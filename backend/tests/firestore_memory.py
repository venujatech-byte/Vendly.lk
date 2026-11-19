"""Exercise real Firestore SDK transactions without credentials or cloud traffic."""

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

from google.api_core.exceptions import Aborted, FailedPrecondition
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
from google.cloud.firestore_v1 import types
from google.cloud.firestore_v1._helpers import decode_dict, decode_value, encode_dict


class MemoryFirestore:
    """Replace transport only; SDK transaction ordering and retries stay real."""

    def __init__(self):
        self.client = firestore.Client(project="demo-vendly-tests", credentials=AnonymousCredentials())
        self.documents = {}
        self.versions = {}
        self.reads = {}
        self.read_states = {}
        self.attempts = 0
        self.before_commit = None
        self.commits = 0
        rpc = Mock()
        rpc.begin_transaction.side_effect = self.begin
        rpc.batch_get_documents.side_effect = self.get_documents
        rpc.run_query.side_effect = self.query
        rpc.commit.side_effect = self.commit
        self.client._firestore_api_internal = rpc

    def put(self, path, data):
        self.documents[path] = deepcopy(data)
        self.versions[path] = self.versions.get(path, 0) + 1

    def begin(self, request, **kwargs):
        self.attempts += 1
        transaction = str(self.attempts).encode()
        self.reads[transaction] = {}
        return types.BeginTransactionResponse(transaction=transaction)

    def snapshot(self, name, transaction=None, documents=None):
        path = name.split("/documents/", 1)[1]
        if transaction:
            self.reads[transaction][path] = self.versions.get(path, 0)
        documents = self.documents if documents is None else documents
        if path not in documents:
            return None
        return types.Document(
            name=name, fields=encode_dict(deepcopy(documents[path])),
            update_time=datetime.fromtimestamp(self.versions[path], timezone.utc),
        )

    def get_documents(self, request, **kwargs):
        # Honor pinned batch reads while returning normal SDK snapshots.
        read_time = request.get("read_time") or datetime.now(timezone.utc)
        if not request.get("read_time"):
            self.read_states[read_time] = deepcopy(self.documents)
        documents = self.read_states[read_time]
        for name in request["documents"]:
            document = self.snapshot(name, request.get("transaction"), documents)
            if document is None:
                yield types.BatchGetDocumentsResponse(missing=name, read_time=read_time)
            else:
                yield types.BatchGetDocumentsResponse(found=document, read_time=read_time)

    def query(self, request, **kwargs):
        query = request["structured_query"]
        parent = request["parent"]
        # Root collection queries already include the terminal /documents in their parent.
        prefix = f"{parent}/" if parent.endswith("/documents") or "/documents/" in parent else f"{parent}/documents/"
        prefix += query.from_[0].collection_id + "/"
        # Support the existing AND/equality product filters without silently ignoring composite queries.
        filters = list(query.where.composite_filter.filters) or [query.where]
        if query.where.composite_filter.filters:
            assert query.where.composite_filter.op == types.StructuredQuery.CompositeFilter.Operator.AND
        conditions = []
        for item in filters:
            field = item.field_filter.field.field_path
            if field:
                assert item.field_filter.op == types.StructuredQuery.FieldFilter.Operator.EQUAL
                conditions.append((field, decode_value(item.field_filter.value, self.client)))
        matches = []
        read_time = request.get("read_time")
        documents = self.read_states[read_time] if read_time else self.documents
        for path, data in list(documents.items()):
            name = f"{self.client._database_string}/documents/{path}"
            if name.startswith(prefix) and "/" not in name[len(prefix):] and all(data.get(field) == expected for field, expected in conditions):
                matches.append((name, data))
        # Match the server's document-name tie-breaker and snapshot cursor across report pages.
        orders = list(query.order_by)
        if not any(order.field.field_path == "__name__" for order in orders):
            orders.append(types.StructuredQuery.Order(
                field=types.StructuredQuery.FieldReference(field_path="__name__"),
                direction=orders[-1].direction if orders else types.StructuredQuery.Direction.ASCENDING,
            ))

        def value_for(item, field_path):
            return item[0] if field_path == "__name__" else item[1][field_path]

        for order in reversed(orders):
            field_path = order.field.field_path
            if field_path != "__name__":
                matches = [item for item in matches if field_path in item[1]]
            matches.sort(key=lambda item: value_for(item, field_path), reverse=order.direction == types.StructuredQuery.Direction.DESCENDING)

        if query.start_at.values:
            cursor = [value.reference_value or decode_value(value, self.client) for value in query.start_at.values]

            def after_cursor(item):
                for order, value in zip(orders, cursor):
                    actual = value_for(item, order.field.field_path)
                    if actual != value:
                        return actual < value if order.direction == types.StructuredQuery.Direction.DESCENDING else actual > value
                return query.start_at.before

            matches = [item for item in matches if after_cursor(item)]
        if query.limit:
            matches = matches[:query.limit]
        for name, _data in matches:
            yield types.RunQueryResponse(document=self.snapshot(name, request.get("transaction"), documents))

    def commit(self, request, **kwargs):
        # Inject a real competing state change immediately before the first commit.
        if self.before_commit:
            change, self.before_commit = self.before_commit, None
            change(self)
        for path, version in self.reads.get(request.get("transaction"), {}).items():
            if self.versions.get(path, 0) != version:
                raise Aborted("Concurrent write; transaction must retry")
        # Apply write preconditions before any mutation, as a Firestore commit does.
        for write in request["writes"]:
            expected_time = write.current_document.update_time
            if expected_time:
                path = write.update.name.split("/documents/", 1)[1]
                if self.versions.get(path, 0) != int(expected_time.timestamp()):
                    raise FailedPrecondition("Document changed since authorization")
        for write in request["writes"]:
            if write.delete:
                path = write.delete.split("/documents/", 1)[1]
                self.documents.pop(path, None)
                self.versions[path] = self.versions.get(path, 0) + 1
            else:
                path = write.update.name.split("/documents/", 1)[1]
                data = decode_dict(write.update.fields, self.client)
                if write.update_mask.field_paths:
                    data = {**self.documents.get(path, {}), **data}
                self.put(path, data)
        self.commits += 1
        return types.CommitResponse(
            write_results=[types.WriteResult() for _ in request["writes"]],
        )


