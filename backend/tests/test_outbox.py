from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock
import pytest
from src.jobs.dispatcher import dispatch_once,reconcile_once
from rq.exceptions import DuplicateJobError

class Cursor:
    def __aiter__(self):
        async def generate():
            yield {'_id':'stable-job-id','kind':'evaluation','target_id':'revision'}
        return generate()

@pytest.mark.asyncio
async def test_dispatch_replay_does_not_enqueue_twice():
    db=SimpleNamespace(outbox=SimpleNamespace(find=Mock(return_value=Cursor()),update_one=AsyncMock()))
    queue=SimpleNamespace(fetch_job=Mock(return_value=object()),enqueue=Mock())
    await dispatch_once(db,queue)
    queue.enqueue.assert_not_called()
    db.outbox.update_one.assert_awaited_once()

@pytest.mark.asyncio
async def test_crash_before_ack_is_safe_to_replay():
    update=AsyncMock(side_effect=RuntimeError('simulated database disconnect'))
    db=SimpleNamespace(outbox=SimpleNamespace(find=Mock(return_value=Cursor()),update_one=update))
    queue=SimpleNamespace(fetch_job=Mock(return_value=None),enqueue=Mock())
    with pytest.raises(RuntimeError): await dispatch_once(db,queue)
    assert queue.enqueue.call_args.kwargs['job_id']=='stable-job-id'
    queue.fetch_job.return_value=object()
    update.side_effect=None
    await dispatch_once(db,queue)
    assert queue.enqueue.call_count==1

@pytest.mark.asyncio
async def test_competing_dispatcher_unique_enqueue_is_acknowledged():
    db=SimpleNamespace(outbox=SimpleNamespace(find=Mock(return_value=Cursor()),update_one=AsyncMock()))
    queue=SimpleNamespace(fetch_job=Mock(return_value=None),enqueue=Mock(side_effect=DuplicateJobError('already queued')))
    await dispatch_once(db,queue)
    assert queue.enqueue.call_args.kwargs['unique'] is True
    db.outbox.update_one.assert_awaited_once()

@pytest.mark.asyncio
@pytest.mark.parametrize('lost',[True,False])
async def test_reconciliation_only_replays_lost_jobs(lost):
    db=SimpleNamespace(jobs=SimpleNamespace(find=Mock(return_value=Cursor())),outbox=SimpleNamespace(update_one=AsyncMock()))
    queue=SimpleNamespace(fetch_job=Mock(return_value=None if lost else object()))
    await reconcile_once(db,queue)
    db.jobs.find.assert_called_once_with({'status':{'$in':['queued','running']}})
    assert db.outbox.update_one.await_count==int(lost)

@pytest.mark.asyncio
async def test_queue_failure_leaves_outbox_pending():
    db=SimpleNamespace(outbox=SimpleNamespace(find=Mock(return_value=Cursor()),update_one=AsyncMock()))
    queue=SimpleNamespace(fetch_job=Mock(return_value=None),enqueue=Mock(side_effect=ConnectionError('offline')))
    with pytest.raises(ConnectionError): await dispatch_once(db,queue)
    db.outbox.update_one.assert_not_awaited()
