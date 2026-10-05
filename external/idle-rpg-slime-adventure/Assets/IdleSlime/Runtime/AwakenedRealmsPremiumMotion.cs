using System;
using System.Collections;
using System.Collections.Generic;
using IdleSlime.Core;
using UnityEngine;
using UnityEngine.UI;

namespace IdleSlime.Runtime {
 /// <summary>DOTween-compatible easing curve set, implemented locally so the runtime has no hard dependency.</summary>
 public enum MotionEase { Linear, OutQuad, OutCubic, OutBack, InQuad, InCubic }

 /// <summary>Pure data + sampling core. A future DOTween adapter can map every field one-to-one onto DOTween.</summary>
 public sealed class MotionTween {
  public float Duration;
  public float Delay;
  public MotionEase Ease = MotionEase.OutCubic;
  public bool Unscaled = true;
  public Action<float> Apply;
  public Action Complete;

  public IEnumerator Run(){
   if(Delay>0f)yield return Wait(Delay);
   float t=0f;
   var d=Mathf.Max(0.0001f,Duration);
   while(t<d){
    t+=Unscaled?Time.unscaledDeltaTime:Time.deltaTime;
    float p=Evaluate(Ease,Mathf.Clamp01(t/d));
    if(Apply!=null)Apply(p);
    yield return null;
   }
   if(Apply!=null)Apply(1f);
   if(Complete!=null)Complete();
  }

  static IEnumerator Wait(float seconds){
   float t=0f;
   while(t<seconds){t+=Time.unscaledDeltaTime;yield return null;}
  }

  public static float Evaluate(MotionEase e,float x){
   switch(e){
    case MotionEase.OutQuad: return 1f-(1f-x)*(1f-x);
    case MotionEase.OutCubic: return 1f-Mathf.Pow(1f-x,3f);
    case MotionEase.OutBack: { const float c1=1.70158f; const float c3=c1+1f; return 1f+c3*Mathf.Pow(x-1f,3f)+c1*Mathf.Pow(x-1f,2f); }
    case MotionEase.InQuad: return x*x;
    case MotionEase.InCubic: return x*x*x;
    default: return x;
   }
  }
 }

 /// <summary>Shared canvas-group helpers for runtime-built UI.</summary>
 public static class MotionTargets {
  public static CanvasGroup EnsureCanvasGroup(GameObject go){
   var cg=go.GetComponent<CanvasGroup>();
   if(cg==null)cg=go.AddComponent<CanvasGroup>();
   return cg;
  }
 }

 /// <summary>Cinematic motion primitives used by IdleSlimeUI. All unscaled-time and coroutine based.</summary>
 public sealed class AwakenedRealmsPremiumMotion : MonoBehaviour {
  static AwakenedRealmsPremiumMotion instance;
  public static AwakenedRealmsPremiumMotion Instance {
   get {
    if(instance==null){
     var go=new GameObject("AwakenedRealmsPremiumMotion");
     DontDestroyOnLoad(go);
     instance=go.AddComponent<AwakenedRealmsPremiumMotion>();
    }
    return instance;
   }
  }

  public Coroutine Play(MotionTween tween){
   return StartCoroutine(tween.Run());
  }

  /// <summary>Staggered card/panel entrances so screens never appear as a static wall.</summary>
  public void Entrance(RectTransform target,int order,Vector2 offset){
   if(target==null)return;
   var cg=MotionTargets.EnsureCanvasGroup(target.gameObject);
   var end=target.anchoredPosition;
   var start=end+offset;
   var delay=order*MotionTokens.EntranceStagger;
   target.anchoredPosition=start;
   cg.alpha=0f;
   Play(new MotionTween{Duration=MotionTokens.PanelReveal,Delay=delay,Ease=MotionEase.OutCubic,
    Apply=p=>{ if(target==null)return; target.anchoredPosition=Vector2.LerpUnclamped(start,end,p); cg.alpha=p; }});
  }

  public void Pop(RectTransform target,float scale,float duration){
   if(target==null)return;
   var peak=Vector3.one*(1f+scale);
   Play(new MotionTween{Duration=duration,Ease=MotionEase.OutCubic,
    Apply=p=>{ if(target==null)return;
     float k=p<0.5f?Mathf.Lerp(0f,1f,p*2f):Mathf.Lerp(1f,0f,(p-0.5f)*2f);
     target.localScale=Vector3.LerpUnclamped(Vector3.one,peak,k); }});
  }

  public void Punch(RectTransform target,float strength,float duration){
   if(target==null)return;
   var baseScale=target.localScale;
   Play(new MotionTween{Duration=duration,Ease=MotionEase.OutQuad,
    Apply=p=>{ if(target==null)return;
     float k=Mathf.Sin(p*Mathf.PI)*(1f-p*0.35f);
     target.localScale=baseScale*(1f+strength*k); }});
  }

  public void Shake(RectTransform target,float amplitude,float duration){
   if(target==null)return;
   var basePos=target.anchoredPosition;
   var seed=UnityEngine.Random.insideUnitCircle;
   Play(new MotionTween{Duration=duration,Ease=MotionEase.Linear,
    Apply=p=>{ if(target==null)return;
     float fade=1f-p;
     var jitter=new Vector2(seed.x*Mathf.Sin(p*31f),seed.y*Mathf.Cos(p*47f))*amplitude*fade;
     target.anchoredPosition=basePos+jitter; },
    Complete=()=>{ if(target!=null)target.anchoredPosition=basePos; }});
  }

  /// <summary>Floating damage/readout popup that rises, scales, and dissolves.</summary>
  public void Popup(RectTransform target,Vector2 from,Vector2 to,float duration,Action onDone){
   if(target==null)return;
   var cg=MotionTargets.EnsureCanvasGroup(target.gameObject);
   cg.alpha=0f;
   target.anchoredPosition=from;
   Play(new MotionTween{Duration=duration,Ease=MotionEase.OutCubic,
    Apply=p=>{ if(target==null)return;
     target.anchoredPosition=Vector2.LerpUnclamped(from,to,p);
     cg.alpha=Mathf.Clamp01(p*3f)*(1f-Mathf.Clamp01((p-0.7f)/0.3f));
     var s=1f+0.25f*Mathf.Sin(p*Mathf.PI);
     target.localScale=new Vector3(s,s,1f); },
    Complete=()=>{ if(onDone!=null)onDone(); }});
  }

  /// <summary>Layered reveal across a PanelStyle: halo -> edge -> body -> sheen.</summary>
  public void RevealLayers(IList<RectTransform> layers){
   if(layers==null)return;
   for(int i=0;i<layers.Count;i++){
    var l=layers[i]; if(l==null)continue;
    var cg=MotionTargets.EnsureCanvasGroup(l.gameObject);
    cg.alpha=0f;
    int order=i;
    Play(new MotionTween{Duration=MotionTokens.PanelReveal*0.85f,Delay=order*0.05f,Ease=MotionEase.OutQuad,
     Apply=p=>{ if(l==null)return; cg.alpha=p; }});
   }
  }
 }
}
