from typing import Optional

from batch import NewBatch, OpenBatch
from command import CommandPlan


class InMemoryStore:

    def __init__(self):
        self.next_batch_id = 1
        self.next_command_id = 1
        self.batches = {}

    def store_batch(self, new_batch: NewBatch) -> OpenBatch:
        command_plans = {}
        for command in new_batch.commands:
            command_plans[self.next_command_id] = CommandPlan(self.next_command_id, command)
            self.next_command_id += 1
        open_batch = OpenBatch(self.next_batch_id,
                               command_plans,
                               command_finishes={})
        self.next_batch_id += 1
        self.batches[open_batch.id] = open_batch
        return open_batch

    def get_batch(self, id: int) -> Optional[OpenBatch]:
        return self.batches[id]
