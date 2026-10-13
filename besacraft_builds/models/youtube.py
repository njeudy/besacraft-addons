"""Reading a YouTube address, for the models that hold one."""

import re

# Les cinq formes d'adresse qu'on colle depuis YouTube : l'identifiant fait toujours
# onze caractères de ce jeu-là, quel que soit le préfixe.
YOUTUBE_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^#]*&)?v=|shorts/|embed/|live/)"
    r"|youtu\.be/)([A-Za-z0-9_-]{11})")


def youtube_id(url):
    """The 11-character video id of a YouTube address, or False."""
    trouve = YOUTUBE_RE.search(url or "")
    return trouve.group(1) if trouve else False
