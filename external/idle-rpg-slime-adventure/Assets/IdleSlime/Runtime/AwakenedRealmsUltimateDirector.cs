using System;
using System.Collections;
using System.Collections.Generic;
using IdleSlime.Core;
using UnityEngine;
using UnityEngine.UI;

namespace IdleSlime.Runtime {
 /// <summary>Runtime director for lore-bound anime-scale ultimate set pieces. Consumes the
 /// Unity-free UltimatePresentation catalog and renders the full cinematic -- letterbox, faction
 /// wash, cut-in banner, time-freeze, afterimage impact beats, environment response, finisher
 /// card, recovery -- entirely through coroutines and MotionTween. No DOTween, no combat writes:
 /// damage/outcomes remain owned by the authoritative BattleResult/BattlePresentationPlan.</summary>
 public sealed class AwakenedRealmsUltimateDirector : MonoBehaviour {
  static AwakenedRealmsUltimateDirector instance;
  public static AwakenedRealmsUltimateDirector Instance {
   get {
    if(instance==null){
     var go=new GameObject("AwakenedRealmsUltimateDirector");
     DontDestroyOnLoad(go);
     instance=go.AddComponent<AwakenedRealmsUltimateDirector>();
    }
    return instance;
   }
  }

  /// <summary>True while an ultimate cinematic occupies the screen.</summary>
  public bool IsPlaying{get;private set;}

  AwakenedRealmsPremiumMotion Motion{get{return AwakenedRealmsPremiumMotion.Instance;}}
  readonly List<RectTransform> live=new List<RectTransform>();

  static Color C(ThemeColor t){return Hex(t.Hex);}
  static Color C(ThemeColor t,float a){var c=Hex(t.Hex);c.a=a;return c;}
  static Color Hex(string hex){
   string h=hex.TrimStart('#');
   float r=Convert.ToInt32(h.Substring(0,2),16)/255f;
   float g=Convert.ToInt32(h.Substring(2,2),16)/255f;
   float b=Convert.ToInt32(h.Substring(4,2),16)/255f;
   float a=h.Length>=8?Convert.ToInt32(h.Substring(6,2),16)/255f:1f;
   return new Color(r,g,b,a);
  }

  /// <summary>Plays the full ultimate cinematic on top of <paramref name="stage"/>. The parent
  /// transform is typically the battle content area; the director builds its own overlay canvas
  /// space inside it and cleans everything up when the sequence ends.</summary>
  public Coroutine Play(UltimatePresentation ultimate,RectTransform stage,RectTransform focusCard,float speed,Action onComplete){
   if(ultimate==null){if(onComplete!=null)onComplete();return null;}
   if(IsPlaying)StopAllCoroutines();
   foreach(var r in live)if(r!=null)Destroy(r.gameObject);
   live.Clear();
   return StartCoroutine(RunSequence(ultimate,stage,focusCard,Mathf.Max(0.5f,speed),onComplete));
  }

  IEnumerator RunSequence(UltimatePresentation u,RectTransform stage,RectTransform focusCard,float speed,Action onComplete){
   IsPlaying=true;
   live.Clear();
   float d(UltimatePhase p){return u.PhaseDuration(p)/speed;}

   // --- Fullscreen stage ------------------------------------------------------
   var overlay=Rect("UltimateOverlay",stage,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
   live.Add(overlay);
   var veil=Rect("FactionVeil",overlay,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
   var veilImg=Img(veil,C(u.FactionToken.Aura,0f));

   var topBar=Rect("LetterboxTop",overlay,new Vector2(0,1),new Vector2(1,1),Vector2.zero,Vector2.zero);
   var botBar=Rect("LetterboxBot",overlay,new Vector2(0,0),new Vector2(1,0),Vector2.zero,Vector2.zero);
   var topImg=Img(topBar,C(AwakenedRealmsVisualTheme.VoidBase,0f));
   var botImg=Img(botBar,C(AwakenedRealmsVisualTheme.VoidBase,0f));
   float barFrac=0.10f;

   var realm=Rect("RealmMessage",overlay,new Vector2(.06f,.84f),new Vector2(.94f,.90f),Vector2.zero,Vector2.zero);
   var realmText=Txt(realm,"",20,TextAnchor.MiddleCenter,C(AwakenedRealmsVisualTheme.EchoCyan),FontStyle.Bold);

   // --- Anticipation: letterbox + faction wash rises ---------------------------
   yield return Tween(d(UltimatePhase.Anticipation),MotionEase.OutCubic,p=>{
    topImg.color=C(AwakenedRealmsVisualTheme.VoidBase,0.92f*p);
    botImg.color=C(AwakenedRealmsVisualTheme.VoidBase,0.92f*p);
    topBar.anchorMin=new Vector2(0,1f-barFrac*p);botBar.anchorMax=new Vector2(1,barFrac*p);
    veilImg.color=C(u.FactionToken.Aura,0.16f*p);
    realmText.text=p>0.35f?u.SystemAlert:"";
   });
   if(focusCard!=null)Motion.Punch(focusCard,0.10f,0.30f);

   // --- Cut-in: signature banner slams in with glyph + name --------------------
   var cut=Rect("CutIn",overlay,new Vector2(-1.2f,.38f),new Vector2(-0.2f,.72f),Vector2.zero,Vector2.zero);
   Panelify(cut,u);
   var glyph=Txt(cut,u.CutInGlyph,64,TextAnchor.MiddleCenter,C(u.FactionToken.Core),FontStyle.Bold);
   Set(glyph.rectTransform,new Vector2(.02f,.30f),new Vector2(.22f,.92f),Vector2.zero,Vector2.zero);
   var name=Txt(cut,u.SignatureName,30,TextAnchor.MiddleLeft,Color.white,FontStyle.Bold);
   Set(name.rectTransform,new Vector2(.25f,.52f),new Vector2(.97f,.92f),Vector2.zero,Vector2.zero);
   var sub=Txt(cut,u.FinisherLine+"  "+EchoLanguage.Divider+"  "+u.UltimateSkill.Name.ToUpper(),17,TextAnchor.MiddleLeft,C(u.FactionToken.Thread),FontStyle.Bold);
   Set(sub.rectTransform,new Vector2(.25f,.14f),new Vector2(.97f,.50f),Vector2.zero,Vector2.zero);
   var fate=Txt(cut,u.FateFragment,15,TextAnchor.MiddleLeft,C(AwakenedRealmsVisualTheme.InkMuted),FontStyle.Italic);
   Set(fate.rectTransform,new Vector2(.25f,.02f),new Vector2(.97f,.20f),Vector2.zero,Vector2.zero);
   yield return Tween(d(UltimatePhase.CutIn),MotionEase.OutBack,p=>{
    cut.anchorMin=new Vector2(Mathf.Lerp(-1.2f,0.02f,p),.38f);
    cut.anchorMax=new Vector2(Mathf.Lerp(-0.2f,0.98f,p),.72f);
   });

   // --- Time dilation: freeze frame, glyph watermark, system alert --------------
   var stamp=Txt(overlay,u.FactionToken.Sigil,320,TextAnchor.MiddleCenter,C(u.FactionToken.Core,0f),FontStyle.Bold);
   Set(stamp.rectTransform,new Vector2(.15f,.10f),new Vector2(.85f,.85f),Vector2.zero,Vector2.zero);
   realmText.text=u.SystemAlert;
   float zoom=CameraZoom(u.CameraMove);
   yield return Tween(d(UltimatePhase.TimeDilation),MotionEase.OutQuad,p=>{
    stamp.color=C(u.FactionToken.Core,0.18f*p);
    stamp.rectTransform.localScale=Vector3.one*(1f+zoom*0.10f*p);
    veilImg.color=C(u.FactionToken.Aura,(0.16f+0.14f*p));
   });

   // --- Impact: afterimage strikes + camera language + shake --------------------
   var strikes=new List<RectTransform>();
   for(int i=0;i<u.AfterimageCount;i++){
   var ghost=Rect("Afterimage_"+i,overlay,new Vector2(.20f+.06f*(i%4),.30f+.05f*(i%3)),new Vector2(.42f+.06f*(i%4),.55f+.05f*(i%3)),Vector2.zero,Vector2.zero);
    var gi=Img(ghost,C(u.FactionToken.Core,0f));
    gi.raycastTarget=false;
    var gt=Txt(ghost,u.Hero.Name.Substring(0,1),120,TextAnchor.MiddleCenter,new Color(1f,1f,1f,0f),FontStyle.Bold);
    Set(gt.rectTransform,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
    strikes.Add(ghost);
   }
   float impactDur=d(UltimatePhase.Impact);
   float per=impactDur/Mathf.Max(1,u.ImpactBeats.Length);
  for(int b=0;b<u.ImpactBeats.Length;b++){
   var beat=u.ImpactBeats[b];
    Play(new MotionTween{Duration=per,Ease=MotionEase.OutCubic,
     Apply=p=>{
      for(int k=0;k<strikes.Count;k++){
       var g=strikes[k];if(g==null)continue;
       float idx=k;
       float lit=Mathf.Clamp01(1f-Mathf.Abs(idx-(float)(p*strikes.Count))/0.9f);
       g.GetComponent<Image>().color=C(u.FactionToken.Core,0.30f*lit);
       var gt=g.GetComponentInChildren<Text>();if(gt!=null)gt.color=new Color(1f,1f,1f,0.55f*lit);
      }}});
    if(beat.DelaySeconds>0f)yield return Wait(beat.DelaySeconds/speed);
    var fx=Rect("Hit_"+beat.Id,overlay,new Vector2(.30f,.30f),new Vector2(.70f,.66f),Vector2.zero,Vector2.zero);
    var flash=Img(fx,new Color(1f,1f,1f,0.85f));
    flash.raycastTarget=false;
    var label=Txt(fx,beat.Motion.ToUpper()+"  x"+beat.HitCount,22,TextAnchor.MiddleCenter,C(u.FactionToken.Core),FontStyle.Bold);
    Set(label.rectTransform,new Vector2(0,-.18f),new Vector2(1,.05f),Vector2.zero,Vector2.zero);
    Play(new MotionTween{Duration=per*0.7f,Ease=MotionEase.OutQuad,
     Apply=p=>{if(fx==null)return;flash.color=new Color(1f,1f,1f,0.85f*(1f-p));fx.localScale=Vector3.one*(1f+p*0.55f);},
     Complete=()=>{if(fx!=null)Destroy(fx.gameObject);}});
    if(stage!=null)Motion.Shake(stage,u.ShakeAmplitude/speed,per*0.5f);
    if(focusCard!=null)Motion.Punch(focusCard,0.07f,per*0.5f);
    yield return Wait(per*0.55f);
   }
   foreach(var g in strikes)if(g!=null)Destroy(g.gameObject);
   strikes.Clear();

  // --- Environment response: named hooks become layered washes -----------------
   string envLine=EnvironmentLine(u);
   yield return Tween(d(UltimatePhase.EnvironmentResponse),MotionEase.OutQuad,p=>{
    float envAlpha=Mathf.Sin(p*Mathf.PI);
    veilImg.color=C(u.FactionToken.Aura,0.30f+0.20f*envAlpha);
    // Hook names are surfaced as Realm-language subtitles so the data contract is visible.
    realmText.text=p>0.15f?envLine:"";
   });
   string EnvironmentLine(UltimatePresentation x){
    var c=x.EnvironmentCues;
    string line=c.Length>0?("[ENV "+c[0].Hook.ToUpperInvariant()+"]"):"[ENV]";
    for(int i=1;i<c.Length;i++)line+="  "+EchoLanguage.Divider+"  ["+c[i].Hook.ToUpperInvariant()+"]";
    return line;
   }

   // --- Finisher: gold/signature card + fade ------------------------------------
   var fin=Rect("Finisher",overlay,new Vector2(.18f,.40f),new Vector2(.82f,.62f),Vector2.zero,Vector2.zero);
   Panelify(fin,u);
   var ft=Txt(fin,u.FinisherLine,32,TextAnchor.MiddleCenter,C(u.RarityToken.Glow),FontStyle.Bold);
   Set(ft.rectTransform,new Vector2(.05f,.30f),new Vector2(.95f,.80f),Vector2.zero,Vector2.zero);
   var fs=Txt(fin,u.SignatureLine,16,TextAnchor.MiddleCenter,C(u.FactionToken.Thread),FontStyle.Italic);
   Set(fs.rectTransform,new Vector2(.05f,.05f),new Vector2(.95f,.34f),Vector2.zero,Vector2.zero);
   yield return Tween(d(UltimatePhase.Finisher),MotionEase.OutBack,p=>{
    fin.localScale=Vector3.one*(0.6f+0.4f*p);
    var cg=MotionTargets.EnsureCanvasGroup(fin.gameObject);cg.alpha=p;
   });

   // --- Recovery: veil lifts, letterbox retracts, world resumes -----------------
   yield return Tween(d(UltimatePhase.Recovery),MotionEase.InQuad,p=>{
    topImg.color=C(AwakenedRealmsVisualTheme.VoidBase,0.92f*(1f-p));
    botImg.color=C(AwakenedRealmsVisualTheme.VoidBase,0.92f*(1f-p));
    topBar.anchorMin=new Vector2(0,1f-barFrac*(1f-p));botBar.anchorMax=new Vector2(1,barFrac*(1f-p));
    veilImg.color=C(u.FactionToken.Aura,(0.30f)*(1f-p));
    stamp.color=C(u.FactionToken.Core,0.18f*(1f-p));
    realmText.text=p<0.6f?u.RecoveryMotif:"";
   });

   foreach(var r in live)if(r!=null)Destroy(r.gameObject);
   live.Clear();
   IsPlaying=false;
   if(onComplete!=null)onComplete();
  }

  float CameraZoom(UltimateCameraMove m){
   switch(m){
    case UltimateCameraMove.ZoomSnap: return 1.6f;
    case UltimateCameraMove.CrashZoom: return 1.4f;
    case UltimateCameraMove.PushIn: return 0.9f;
    case UltimateCameraMove.CraneRise: return 0.8f;
    case UltimateCameraMove.OrbitSlash: return 1.1f;
    case UltimateCameraMove.WhipPan: return 1.3f;
    case UltimateCameraMove.TrackingShot: return 1.0f;
    case UltimateCameraMove.OverheadSeal: return 0.7f;
    default: return 1f;
   }
  }

  IEnumerator Tween(float duration,MotionEase ease,Action<float> apply){
   float t=0f;var d=Mathf.Max(0.0001f,duration);
   while(t<d){t+=Time.unscaledDeltaTime;if(apply!=null)apply(MotionTween.Evaluate(ease,Mathf.Clamp01(t/d)));yield return null;}
   if(apply!=null)apply(1f);
  }
  IEnumerator Wait(float s){float t=0f;while(t<s){t+=Time.unscaledDeltaTime;yield return null;}}
  Coroutine Play(MotionTween t){return Motion.Play(t);}

  static void Set(RectTransform r,Vector2 amin,Vector2 amax,Vector2 omin,Vector2 omax){r.anchorMin=amin;r.anchorMax=amax;r.offsetMin=omin;r.offsetMax=omax;}
  static RectTransform Rect(string n,Transform p,Vector2 amin,Vector2 amax,Vector2 omin,Vector2 omax){var g=new GameObject(n,typeof(RectTransform));var r=(RectTransform)g.transform;r.SetParent(p,false);Set(r,amin,amax,omin,omax);return r;}
  static Image Img(RectTransform r,Color c){var i=r.GetComponent<Image>()??r.gameObject.AddComponent<Image>();i.color=c;i.raycastTarget=false;return i;}
  static Text Txt(Transform p,string v,int size,TextAnchor a,Color c,FontStyle s){var g=new GameObject("Text",typeof(RectTransform),typeof(Text));g.transform.SetParent(p,false);var t=g.GetComponent<Text>();t.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");if(t.font==null)t.font=Resources.GetBuiltinResource<Font>("Arial.ttf");t.text=v;t.fontSize=size;t.alignment=a;t.color=c;t.fontStyle=s;t.horizontalOverflow=HorizontalWrapMode.Wrap;t.verticalOverflow=VerticalWrapMode.Overflow;return t;}
  static void Panelify(RectTransform r,UltimatePresentation u){
   var style=AwakenedRealmsVisualTheme.Style("banner_hero");
   bool first=true;
   foreach(var layer in style.Layers){
    RectTransform lr=first?r:Rect("Layer_"+layer.Key,r,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
    if(!first)Set(lr,Vector2.zero,Vector2.one,new Vector2(layer.InsetPixels,layer.InsetPixels),new Vector2(-layer.InsetPixels,-layer.InsetPixels));
    var img=lr.GetComponent<Image>()??lr.gameObject.AddComponent<Image>();
    img.color=layer.Key=="faction_wash"?C(u.FactionToken.Aura,0.25f):C(layer.Color);
    img.raycastTarget=first;
    first=false;
   }
  }
 }
}
