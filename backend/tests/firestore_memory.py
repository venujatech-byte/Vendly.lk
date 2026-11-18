"""Exercise real Firestore SDK transactions without credentials or cloud traffic."""

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

from google.api_core.exceptions import Aborted, FailedPrecondition
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
from google.cloud.firestore_v1 import types
from google.cloud.firestore_v1._helpers import decode_dict, encode_dict


class MemoryFirestore:
    """Replace transport only; SDK transaction ordering and retries stay real."""

    def __init__(self):
        self.client = firestore.Client(project="demo-vendly-tests", credentials=AnonymousCredentials())
        self.documents = {}
        self.versions = {}
        self.reads = {}
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

    def snapshot(self, name, transaction=None):
        path = name.split("/documents/", 1)[1]
        if transaction:
            self.reads[transaction][path] = self.versions.get(path, 0)
        if path not in self.documents:
            return None
        return types.Document(
            name=name, fields=encode_dict(deepcopy(self.documents[path])),
            update_time=datetime.fromtimestamp(self.versions[path], timezone.utc),
        )

    def get_documents(self, request, **kwargs):
        # Return protobuf snapshots so the SDK builds its normal DocumentSnapshot objects.
        for name in request["documents"]:
            document = self.snapshot(name, request.get("transaction"))
            if document is None:
                yield types.BatchGetDocumentsResponse(missing=name)
            else:
                yield types.BatchGetDocumentsResponse(found=document)

    def query(self, request, **kwargs):
        query = request["structured_query"]
        parent = request["parent"]
        prefix = f"{parent}/documents/" if "/documents/" not in parent else f"{parent}/"
        prefix += query.from_[0].collection_id + "/"
        field = query.where.field_filter.field.field_path
        expected = query.where.field_filter.value.string_value
        matches = []
        for path, data in list(self.documents.items()):
            name = f"{self.client._database_string}/documents/{path}"
            if name.startswith(prefix) and (not field or data.get(field) == expected):
                matches.append((name, data))
        # Match Firestore ordering/limits for notification history without bypassing SDK queries.
        for order in reversed(query.order_by):
            field_path = order.field.field_path
            matches = [item for item in matches if field_path in item[1]]
            matches.sort(key=lambda item: item[1][field_path], reverse=order.direction == types.StructuredQuery.Direction.DESCENDING)
        if query.limit:
            matches = matches[:query.limit]
        for name, _data in matches:
            yield types.RunQueryResponse(document=self.snapshot(name, request.get("transaction")))

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


