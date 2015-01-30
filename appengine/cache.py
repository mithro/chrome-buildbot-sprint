#!/usr/bin/python

"""
>>> CACHE.set("a", 1)
>>> CACHE.get("a")
1
>>> CACHE.delete("a")
>>> CACHE.get("a") is None
True
"""
class Cache(dict):
  """
  >>> marker_a = []
  >>> marker_b = []
  >>> 
  >>> c = Cache()
  >>> c.set("a", marker_a)
  >>> c.set("b", marker_b)
  >>> 
  >>> c["a"] is marker_a
  True
  >>> c.get("a") is marker_a
  True
  >>> c.delete("a")
  >>> c.get("a") is None
  True
  >>> c["b"] is marker_b
  True
  >>> c.get("b") is marker_b
  True
  >>>
  >>> 
  >>> parent = Cache()
  >>> child = Cache(parent=parent)
  >>>
  >>> parent.set("a", marker_a)
  >>> parent.get("a") is marker_a
  True
  >>> child.get("a") is marker_a
  True
  >>> child.get("b") is None
  True
  >>>
  >>> child.set("b", marker_b)
  >>> child.get("b") is marker_b
  True
  >>> parent.get("b") is marker_b
  True
  >>> child.delete("b")
  >>> child.get("b") is None
  True
  >>> parent.get("b") is None
  True
  >>> 
  """

  def __init__(self, parent=None):
    self.parent = parent

  def set(self, key, value, time=None):
    self[key] = value

    # Set on parent also.
    if self.parent:
      self.parent.set(key, value, time)

  def get(self, key):
    # If we don't have the key, try and get it from the parent.
    if not key in self and self.parent:
      v = self.parent.get(key)
      if v is not None:
        self[key] = v

    try:
      return self[key]
    except KeyError:
      return None

  def delete(self, key):
    if key in self:
      del self[key]

    # Delete from parent also.
    if self.parent:
      del self.parent[key]

try:
  from google.appengine.api import memcache
except ImportError:
  memcache = Cache(parent=None)

CACHE = Cache(parent=memcache)

if __name__ == "__main__":
    import doctest
    doctest.testmod()