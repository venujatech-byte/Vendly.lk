from datetime import datetime, timedelta, timezone

from flask import current_app


def _latest_metric(cloudwatch, instance_id, metric_name, unit=None, namespace="AWS/EC2"):
    now = datetime.now(timezone.utc)
    request = {
        "Namespace": namespace,
        "MetricName": metric_name,
        "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
        "StartTime": now - timedelta(minutes=15),
        "EndTime": now,
        "Period": 300,
        "Statistics": ["Average"],
    }
    if unit:
        request["Unit"] = unit
    response = cloudwatch.get_metric_statistics(**request)
    points = response.get("Datapoints") or []
    if not points:
        return None
    return max(points, key=lambda point: point.get("Timestamp", datetime.min.replace(tzinfo=timezone.utc))).get("Average")


def get_aws_server_health():
    """Read lightweight EC2 and CloudWatch health data for the admin panel."""
    region = current_app.config.get("AWS_REGION")
    instance_id = current_app.config.get("AWS_INSTANCE_ID")
    if not region or not instance_id:
        return {
            "configured": False,
            "status": "unconfigured",
            "message": "Set AWS_REGION and AWS_INSTANCE_ID to enable AWS monitoring.",
        }

    try:
        import boto3

        ec2 = boto3.client("ec2", region_name=region)
        cloudwatch = boto3.client("cloudwatch", region_name=region)
        reservations = ec2.describe_instances(InstanceIds=[instance_id]).get("Reservations", [])
        instances = [instance for reservation in reservations for instance in reservation.get("Instances", [])]
        if not instances:
            return {"configured": True, "status": "warning", "message": "EC2 instance was not found."}

        instance = instances[0]
        status_response = ec2.describe_instance_status(InstanceIds=[instance_id]).get("InstanceStatuses", [])
        checks = status_response[0] if status_response else {}
        system_status = checks.get("SystemStatus", {}).get("Status") or "unknown"
        instance_status = checks.get("InstanceStatus", {}).get("Status") or "unknown"
        cpu = _latest_metric(cloudwatch, instance_id, "CPUUtilization", "Percent")
        network_in = _latest_metric(cloudwatch, instance_id, "NetworkIn", "Bytes")
        network_out = _latest_metric(cloudwatch, instance_id, "NetworkOut", "Bytes")
        memory = _latest_metric(cloudwatch, instance_id, "mem_used_percent", "Percent", namespace="CWAgent")
        disk = _latest_metric(cloudwatch, instance_id, "disk_used_percent", "Percent", namespace="CWAgent")
        state = instance.get("State", {}).get("Name", "unknown")
        healthy = state == "running" and system_status in {"ok", "initializing"} and instance_status in {"ok", "initializing"} and (cpu is None or cpu < 90)

        return {
            "configured": True,
            "status": "healthy" if healthy else "warning",
            "region": region,
            "instanceId": instance_id,
            "instanceType": instance.get("InstanceType"),
            "state": state,
            "checks": {"system": system_status, "instance": instance_status},
            "metrics": {
                "cpuPercent": round(cpu, 2) if cpu is not None else None,
                "memoryPercent": round(memory, 2) if memory is not None else None,
                "diskPercent": round(disk, 2) if disk is not None else None,
                "networkInBytes": round(network_in) if network_in is not None else None,
                "networkOutBytes": round(network_out) if network_out is not None else None,
            },
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "note": "Install/configure the CloudWatch Agent for memory and disk metrics." if memory is None or disk is None else None,
        }
    except Exception as error:
        return {
            "configured": True,
            "status": "unavailable",
            "message": "AWS monitoring could not be reached.",
            "detail": str(error)[:240],
        }
