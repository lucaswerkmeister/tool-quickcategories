class FakeSession:

    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response
