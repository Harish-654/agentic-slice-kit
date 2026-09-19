# Mutable default arguments

A default value is evaluated once, when the `def` statement runs, not each time
the function is called. If the default is a mutable object such as a list, every
call that omits the argument shares that one object.

```python
def add(item, bucket=[]):
    bucket.append(item)
    return bucket

add(1)   # [1]
add(2)   # [1, 2]  - the same list as before
```

The usual fix is to use `None` as the default and create the list inside the
function: `if bucket is None: bucket = []`. In this course we always write it
that way, and we mark any other form as wrong in assessments.
