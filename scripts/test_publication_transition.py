from validate_publication_transition import validate_transition

def pointer(day,status='provisional',edition='Morning'):
    return {'date':day,'edition_status':status,'edition':edition,'publication_cycle':'morning'}

def reject(old,new):
    try:validate_transition(old,new)
    except ValueError:return
    raise AssertionError((old,new))
reject(pointer('2026-10-08'),pointer('2026-10-07'))
reject(pointer('2026-10-08','official'),pointer('2026-10-08'))
reject(pointer('2026-10-08','official','Close'),pointer('2026-10-08','official','Close'))
assert validate_transition(pointer('2026-10-08'),pointer('2026-10-08','official','Close'))
assert validate_transition(pointer('2026-10-07','official'),pointer('2026-10-08','official'))
assert validate_transition(pointer('2026-10-07','official','Morning Fallback Final'),pointer('2026-10-07','official','Close'))
print('PUBLICATION TRANSITION REGRESSION PASSED')

reject(pointer('2026-10-08','official'),{'date':'2026-10-09','edition_status':'official','publication_cycle':'close'})
reject(pointer('2026-10-08','official'),pointer('2026-10-09'))

from validate_publish_v2 import validate_current_publication_policy
from validate_publish import Gate
from copy import deepcopy
report={'date':'2026-10-09','edition_status':'official','publication_cycle':{'cycle':'morning','is_final':True,'archive_eligible':True,'market_lens_native_eligible':True}}
def errors(r):
    g=Gate();validate_current_publication_policy(r,'fixture',g);return g.errors
assert not errors(report)
for field,value in [('cycle','close'),('is_final',False),('archive_eligible',False),('market_lens_native_eligible',False)]:
    bad=deepcopy(report);bad['publication_cycle'][field]=value;assert errors(bad),(field,bad)
bad=deepcopy(report);bad['edition_status']='provisional';assert errors(bad)
bad=deepcopy(report);bad['reconstruction']={'is_reconstructed':True};assert errors(bad)
bad['publication_cycle']['market_lens_native_eligible']=False;assert not errors(bad)
legacy=deepcopy(report);legacy['date']='2026-09-24';legacy['edition_status']='provisional';legacy['publication_cycle']['is_final']=False;assert not errors(legacy)
print('MORNING-ONLY PREMERGE POLICY REGRESSION PASSED')
