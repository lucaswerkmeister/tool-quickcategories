import datetime
import mwapi # type: ignore
import mwoauth # type: ignore
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from batch import NewBatch, StoredBatch, OpenBatch, ClosedBatch
from batch_background_runs import BatchBackgroundRuns
from batch_command_records import BatchCommandRecords
from command import CommandPlan, CommandPending, CommandRecord, CommandFinish
from localuser import LocalUser
from store import BatchStore, _local_user_from_session, _now


class InMemoryStore(BatchStore):

    def __init__(self):
        self.next_batch_id = 1
        self.next_command_id = 1
        self.batches = {} # type: Dict[int, StoredBatch]
        self.background_sessions = {} # type: Dict[int, mwapi.Session]

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        created = _now()
        local_user = _local_user_from_session(session)

        command_plans = [] # type: List[CommandRecord]
        for command in new_batch.commands:
            command_plans.append(CommandPlan(self.next_command_id, command))
            self.next_command_id += 1

        open_batch = OpenBatch(self.next_batch_id,
                               local_user,
                               local_user.domain,
                               created,
                               created,
                               _BatchCommandRecordsList(command_plans, self),
                               _BatchBackgroundRunsList([], self))
        self.next_batch_id += 1
        self.batches[open_batch.id] = open_batch
        return open_batch

    def get_batch(self, id: int) -> Optional[StoredBatch]:
        stored_batch = self.batches.get(id)
        if stored_batch is None:
            return None

        command_records = cast(_BatchCommandRecordsList, stored_batch.command_records).command_records
        if isinstance(stored_batch, OpenBatch) and \
           all(map(lambda command_record: isinstance(command_record, CommandFinish), command_records)):
            stored_batch = ClosedBatch(stored_batch.id,
                                       stored_batch.local_user,
                                       stored_batch.domain,
                                       stored_batch.created,
                                       stored_batch.last_updated,
                                       stored_batch.command_records,
                                       stored_batch.background_runs)
            self.batches[id] = stored_batch
        return stored_batch

    def get_latest_batches(self) -> Sequence[StoredBatch]:
        return [cast(StoredBatch, self.get_batch(id)) for id in sorted(self.batches.keys(), reverse=True)[:10]]

    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None:
        started = _now()
        local_user = _local_user_from_session(session)
        background_runs = cast(_BatchBackgroundRunsList, batch.background_runs)
        if not background_runs.currently_running():
            background_runs.background_runs.append(((started, local_user), None))
            self.background_sessions[batch.id] = session

    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None:
        stopped = _now()
        if session:
            local_user = _local_user_from_session(session) # type: Optional[LocalUser]
        else:
            local_user = None
        background_runs = cast(_BatchBackgroundRunsList, batch.background_runs)
        if background_runs.currently_running():
            background_runs.background_runs[-1] = (background_runs.background_runs[-1][0], (stopped, local_user))
            del self.background_sessions[batch.id]

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[Tuple[OpenBatch, CommandPending, mwapi.Session]]:
        batches_by_last_updated = [batch for batch in sorted(self.batches.values(), key=lambda batch: batch.last_updated) if batch.background_runs.currently_running()]
        if not batches_by_last_updated:
            return None
        batch = batches_by_last_updated[0]
        assert isinstance(batch, OpenBatch)
        assert isinstance(batch.command_records, _BatchCommandRecordsList)
        for index, command_plan in enumerate(batch.command_records.command_records):
            if not isinstance(command_plan, CommandPlan):
                continue
            command_pending = CommandPending(command_plan.id, command_plan.command)
            batch.command_records.command_records[index] = command_pending
        return batch, command_pending, self.background_sessions[batch.id]


class _BatchCommandRecordsList(BatchCommandRecords):

    def __init__(self, command_records: List[CommandRecord], store: InMemoryStore):
        self.command_records = command_records
        self.store = store

    def get_slice(self, offset: int, limit: int) -> List[CommandRecord]:
        return self.command_records[offset:offset+limit]

    def make_plans_pending(self, offset: int, limit: int) -> List[CommandPending]:
        command_pendings = []
        for index, command_plan in enumerate(self.command_records[offset:offset+limit]):
            if not isinstance(command_plan, CommandPlan):
                continue
            command_pending = CommandPending(command_plan.id, command_plan.command)
            self.command_records[index] = command_pending
            command_pendings.append(command_pending)
        return command_pendings

    def store_finish(self, command_finish: CommandFinish) -> None:
        for index, command_record in enumerate(self.command_records):
            if command_record.id == command_finish.id:
                self.command_records[index] = command_finish
                break
        else:
            raise KeyError('command not found')

    def __len__(self) -> int:
        return len(self.command_records)

    def __eq__(self, value: Any) -> bool:
        return type(value) is _BatchCommandRecordsList and \
            self.command_records == value.command_records


class _BatchBackgroundRunsList(BatchBackgroundRuns):

    def __init__(self, background_runs: List[Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]], store: InMemoryStore):
        self.background_runs = background_runs
        self.store = store

    def get_last(self) -> Optional[Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]]:
        if self.background_runs:
            return self.background_runs[-1]
        else:
            return None

    def get_all(self) -> Sequence[Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]]:
        return self.background_runs

    def __eq__(self, value: Any) -> bool:
        return type(value) is _BatchBackgroundRunsList and \
            self.background_runs == value.background_runs
