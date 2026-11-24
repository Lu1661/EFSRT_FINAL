import os

from libreria import create_app

app = create_app(
    https=os.environ.get("LIBRERIA_HTTPS") == "1",
    proxy=os.environ.get("LIBRERIA_PROXY") == "1",
)
