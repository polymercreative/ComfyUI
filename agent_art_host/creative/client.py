"""Agent SDK. Every mutation renders and returns its visual observation."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class Art:
    def __init__(self, url="http://127.0.0.1:8794"):
        self.url = url.rstrip("/")

    def request(self, route, body=None, timeout=180):
        req = Request(self.url+"/agent-art/"+route,
                      data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(error.read().decode()) from error

    def create(self, name, document):
        return self.request("edit", {"name": name, "document": document})

    def edit(self, name, changes, revision=None):
        return self.request("edit", {"name": name, "changes": changes, "revision": revision})

    def batch(self, name, edits, revision):
        return self.request("edit", {"name": name, "edits": edits, "revision": revision})

    def open(self, name):
        return self.request("document/"+name)

    def image_bytes(self, image):
        with urlopen(self.url+image["url"], timeout=15) as response:
            return response.read()
