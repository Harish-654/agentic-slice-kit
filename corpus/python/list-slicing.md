# List slicing and indexes

Indexes start at 0. A slice `items[start:stop]` includes `start` and excludes
`stop`, so `items[1:3]` is the second and third elements, and its length is
`stop - start`.

```python
items = ["a", "b", "c", "d"]
items[1:3]   # ["b", "c"]
items[:2]    # ["a", "b"]
items[-1]    # "d"
```

A slice always makes a new list, and it never raises `IndexError` for an
out-of-range bound. A single index outside the list does raise `IndexError`.
Most off-by-one mistakes come from forgetting that the stop index is excluded.
