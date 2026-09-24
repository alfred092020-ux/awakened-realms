from __future__ import annotations
import math
from pathlib import Path
from PIL import Image, ImageChops

def compare_images(reference, observed, *, max_normalized_rmse=0.02, max_changed_ratio=0.01):
    reference=str(reference); observed=str(observed)
    with Image.open(reference) as a0, Image.open(observed) as b0:
        a=a0.convert("RGB"); b=b0.convert("RGB")
        dims={"reference":[a.width,a.height],"observed":[b.width,b.height]}
        if a.size!=b.size:
            return {"verdict":"FAIL","reason":"DIMENSION_MISMATCH","dimensions":dims,
                    "metrics":None,"reference_artifact":reference,"observed_artifact":observed}
        diff=ImageChops.difference(a,b)
        hist=diff.histogram()
        pixels=a.width*a.height
        channels=3
        sum_sq=0
        for channel in range(channels):
            h=hist[channel*256:(channel+1)*256]
            sum_sq+=sum((i*i)*count for i,count in enumerate(h))
        rmse=math.sqrt(sum_sq/(pixels*channels)) if pixels else 0.0
        changed=sum(1 for px in diff.getdata() if px!=(0,0,0))
        changed_ratio=changed/pixels if pixels else 0.0
        normalized=rmse/255.0
        verdict="PASS" if normalized<=max_normalized_rmse and changed_ratio<=max_changed_ratio else "FAIL"
        return {"verdict":verdict,"reason":"MEASURED","dimensions":dims,
                "metrics":{"rmse":round(rmse,8),"normalized_rmse":round(normalized,10),
                           "changed_pixels":changed,"total_pixels":pixels,
                           "changed_pixel_ratio":round(changed_ratio,10),
                           "threshold_normalized_rmse":max_normalized_rmse,
                           "threshold_changed_pixel_ratio":max_changed_ratio},
                "reference_artifact":reference,"observed_artifact":observed}
