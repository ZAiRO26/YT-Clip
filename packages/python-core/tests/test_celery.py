from clipforge_core.celery_app import celery_app, noop_task


def test_celery_queues_configured():
    queues = [q.name for q in celery_app.conf.task_queues]
    assert "ingest" in queues
    assert "analysis" in queues
    assert "llm" in queues
    assert "editorial" in queues
    assert "render" in queues
    assert "qa" in queues
    assert "default" in queues


def test_noop_task_execution():
    result = noop_task({"test": "value"})
    assert result["status"] == "ok"
    assert result["payload"] == {"test": "value"}
