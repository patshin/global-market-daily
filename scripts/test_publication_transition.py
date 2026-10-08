from validate_publication_transition import validate_transition

def pointer(day,status='provisional',edition='Morning'):
    return {'date':day,'edition_status':status,'edition':edition}

def reject(old,new):
    try:validate_transition(old,new)
    except ValueError:return
    raise AssertionError((old,new))
reject(pointer('2026-10-08'),pointer('2026-10-07'))
reject(pointer('2026-10-08','official'),pointer('2026-10-08'))
reject(pointer('2026-10-08','official','Close'),pointer('2026-10-08','official','Close'))
assert validate_transition(pointer('2026-10-08'),pointer('2026-10-08','official','Close'))
assert validate_transition(pointer('2026-10-07','official'),pointer('2026-10-08'))
assert validate_transition(pointer('2026-10-07','official','Morning Fallback Final'),pointer('2026-10-07','official','Close'))
print('PUBLICATION TRANSITION REGRESSION PASSED')
