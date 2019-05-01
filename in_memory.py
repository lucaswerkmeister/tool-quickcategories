import datetime
import mwapi # type: ignore
import mwoauth # type: ignore
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from batch import NewBatch, StoredBatch, OpenBatch, ClosedBatch
from batch_background_runs import BatchBackgroundRuns
from batch_command_records import BatchCommandRecords
from command import CommandPlan, CommandPending, CommandRecord, CommandFinish, CommandFailure
from localuser import LocalUser
from store import BatchStore, _local_user_from_session, _now


class InMemoryStore(BatchStore):

    def __init__(self):
        self.next_batch_id = 1
        self.next_command_id = 1
        self.batches = {} # type: Dict[int, StoredBatch]
        self.background_sessions = {} # type: Dict[int, mwapi.Session]
        self.background_suspensions = {} # type: Dict[int, datetime.datetime]

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
                               new_batch.title,
                               created,
                               created,
                               _BatchCommandRecordsList(command_plans, self.next_batch_id, self),
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
                                       stored_batch.title,
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
            self.background_suspensions.pop(batch.id, None)

    def suspend_background(self, batch: StoredBatch, until: datetime.datetime) -> None:
        self.background_suspensions[batch.id] = until

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[Tuple[OpenBatch, CommandPending, mwapi.Session]]:
        batches_by_last_updated = sorted(self.batches.values(), key=lambda batch: batch.last_updated)
        for batch in batches_by_last_updated:
            if not batch.background_runs.currently_running():
                continue
            if batch.id in self.background_suspensions:
                if self.background_suspensions[batch.id] < _now():
                    del self.background_suspensions[batch.id]
                else:
                    continue
            assert isinstance(batch, OpenBatch)
            assert isinstance(batch.command_records, _BatchCommandRecordsList)
            for index, command_plan in enumerate(batch.command_records.command_records):
                if not isinstance(command_plan, CommandPlan):
                    continue
                command_pending = CommandPending(command_plan.id, command_plan.command)
                batch.command_records.command_records[index] = command_pending
                return batch, command_pending, self.background_sessions[batch.id]
        return None


class _BatchCommandRecordsList(BatchCommandRecords):

    def __init__(self, command_records: List[CommandRecord], batch_id: int, store: InMemoryStore):
        self.command_records = command_records
        self.batch_id = batch_id
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

    def make_pendings_planned(self, command_record_ids: List[int]) -> None:
        for index, command_pending in enumerate(self.command_records):
            if not isinstance(command_pending, CommandPending):
                continue
            if command_pending.id not in command_record_ids:
                continue
            command_plan = CommandPlan(command_pending.id, command_pending.command)
            self.command_records[index] = command_plan

    def store_finish(self, command_finish: CommandFinish) -> None:
        for index, command_record in enumerate(self.command_records):
            if command_record.id == command_finish.id:
                self.command_records[index] = command_finish
                break
        else:
            raise KeyError('command not found')

        self.store.batches[self.batch_id].last_updated = _now()

        if isinstance(command_finish, CommandFailure) and \
           command_finish.can_retry_later():
            # append a fresh plan for the same command
            command_plan = CommandPlan(self.store.next_command_id, command_finish.command)
            self.store.next_command_id += 1
            self.command_records.append(command_plan)

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
