import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('profiles renderer aggregates without exporting recovered geometry', () => {
  const output = execFileSync(
    'python3',
    ['-B', '-c', [
      "import sys;sys.path.insert(0,'scripts/logres');from profile_private_map_render_model import profile_root",
      "root={'Width':120,'Height':120,'QuadTreeRoot':{'Grids':[{'Col':2,'Row':3,'DepthOrder':7,'Chips':[{'Id':1,'Vertices':[{'VertexPos':{'PosX':0.0,'PosY':0.0},'UvPoses':[{'UvX':0.5,'UvY':0.25}]},{'VertexPos':{'PosX':10.0,'PosY':0.0},'UvPoses':[{'UvX':1.0,'UvY':0.25}]},{'VertexPos':{'PosX':0.0,'PosY':10.0},'UvPoses':[{'UvX':0.5,'UvY':0.5}]}]}]}]}}",
      "r=profile_root(root,(100,200),(100,200))",
      "assert r['grid']['count']==1",
      "assert r['entities']['Chips']['vertices_per_entity'][0]['value']==3",
      "assert r['entities']['Chips']['uv_pixel_grid_hits']=={'x':3,'y':3}",
      "assert r['entities']['Chips']['triangle_strip_triangle_count_candidate']==1",
      "print('PASS')",
    ].join(';')],
    { encoding: 'utf8' },
  )
  expect(output).toContain('PASS')
})
