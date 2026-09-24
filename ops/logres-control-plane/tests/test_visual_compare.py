import tempfile,sys,unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from logres_visual_compare import compare_images
class VisualCompareTests(unittest.TestCase):
 def img(self,path,size,color):
  Image.new("RGB",size,color).save(path)
 def test_identical_passes(self):
  with tempfile.TemporaryDirectory() as td:
   a=Path(td)/"a.png";b=Path(td)/"b.png";self.img(a,(4,4),(1,2,3));self.img(b,(4,4),(1,2,3))
   r=compare_images(a,b);self.assertEqual("PASS",r["verdict"]);self.assertEqual(0,r["metrics"]["changed_pixels"])
 def test_dimension_mismatch_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   a=Path(td)/"a.png";b=Path(td)/"b.png";self.img(a,(4,4),(0,0,0));self.img(b,(5,4),(0,0,0))
   self.assertEqual("DIMENSION_MISMATCH",compare_images(a,b)["reason"])
 def test_large_difference_fails(self):
  with tempfile.TemporaryDirectory() as td:
   a=Path(td)/"a.png";b=Path(td)/"b.png";self.img(a,(4,4),(0,0,0));self.img(b,(4,4),(255,255,255))
   r=compare_images(a,b);self.assertEqual("FAIL",r["verdict"]);self.assertEqual(1.0,r["metrics"]["changed_pixel_ratio"])
if __name__=="__main__":unittest.main()
