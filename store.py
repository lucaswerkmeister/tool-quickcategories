import mwapi # type: ignore
from typing import List, Optional

from batch import NewBatch, OpenBatch
from command import CommandPlan, CommandRecord


class InMemoryStore:

    def __init__(self):
        self.next_batch_id = 1
        self.next_command_id = 1
        self.batches = {}

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        command_plans = [] # type: List[CommandRecord]
        for command in new_batch.commands:
            command_plans.append(CommandPlan(self.next_command_id, command))
            self.next_command_id += 1

        domain = session.host[len('https://'):]
        response = session.get(action='query',
                               meta='userinfo',
                               uiprop='centralids')
        user_name = response['query']['userinfo']['name']
        local_user_id = response['query']['userinfo']['id']
        global_user_id = response['query']['userinfo']['centralids']['CentralAuth']

        open_batch = OpenBatch(self.next_batch_id,
                               user_name,
                               local_user_id,
                               global_user_id,
                               domain,
                               command_plans)
        self.next_batch_id += 1
        self.batches[open_batch.id] = open_batch
        return open_batch

    def get_batch(self, id: int) -> Optional[OpenBatch]:
        return self.batches.get(id)
