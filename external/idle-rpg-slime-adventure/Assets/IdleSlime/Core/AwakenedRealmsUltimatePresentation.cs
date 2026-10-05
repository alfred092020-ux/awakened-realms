using System;
using System.Collections.Generic;
using System.Linq;

namespace IdleSlime.Core {
 /// <summary>Ordered cinematic phases every ultimate set piece runs through. Kept coarse so the
 /// runtime director can map each phase to camera, VFX, or screen-space hooks without ambiguity.</summary>
 public enum UltimatePhase { Anticipation, CutIn, TimeDilation, Impact, EnvironmentResponse, Finisher, Recovery }

 /// <summary>Camera language tokens. Runtime maps these onto RectTransform/UI hooks; the enum stays
 /// Unity-free so the catalog remains deterministic and testable in edit mode.</summary>
 public enum UltimateCameraMove { PushIn, OrbitSlash, WhipPan, ZoomSnap, CraneRise, TrackingShot, CrashZoom, OverheadSeal }

 /// <summary>How strongly the set piece bends time during TimeDilation. Purely presentational.</summary>
 public enum UltimateTimeScale { Still, Slow, NearStop }

 /// <summary>A single impact beat inside the Impact phase (slashes, volleys, shockwaves).</summary>
 [Serializable]
 public sealed class UltimateImpactBeat {
  public string Id, Motion;
  public int HitCount;
  public float DelaySeconds;
  public UltimateImpactBeat(string id,string motion,int hits,float delay){Id=id;Motion=motion;HitCount=hits;DelaySeconds=delay;}
 }

 /// <summary>Environment response cue: named hook + intensity. Runtime binds hook names to shader,
 /// particle, or screen-space effects; Phase 1 renders them as Realm-language washes and glyphs.</summary>
 [Serializable]
 public sealed class UltimateEnvironmentCue {
  public string Hook;
  public float Intensity;
  public UltimateEnvironmentCue(string hook,float intensity){Hook=hook;Intensity=intensity;}
 }

 /// <summary>The complete lore-bound anime-scale ultimate presentation for one hero. Every field is
 /// data; nothing here mutates combat. Damage/outcomes remain owned by BattleSimulator results.</summary>
 [Serializable]
 public sealed class UltimatePresentation {
  public string HeroId{get;private set;}
  public HeroDefinition Hero{get;private set;}
  public HeroDestiny Destiny{get;private set;}
  public FactionVisualToken FactionToken{get;private set;}
  public RarityVisualToken RarityToken{get;private set;}
  public SkillDefinition UltimateSkill{get;private set;}

  /// <summary>Named signature displayed on the cut-in banner (e.g. "PHOENIX WARDEN: GATE OF EMBERS").</summary>
  public string SignatureName{get;private set;}
  /// <summary>Short spoken/printed signature line under the name.</summary>
  public string SignatureLine{get;private set;}
  /// <summary>Realm-system style alert shown during anticipation, in the voice of narrative SystemMessages.</summary>
  public string SystemAlert{get;private set;}
  /// <summary>Fate fragment quoted from the hero's first timeline; grounds the set piece in destiny.</summary>
  public string FateFragment{get;private set;}

  public UltimateCameraMove CameraMove{get;private set;}
  public UltimateTimeScale TimeScale{get;private set;}
  /// <summary>Seconds of near-frozen time before impact lands (unscaled presentation time).</summary>
  public float FreezeSeconds{get;private set;}
  /// <summary>Cut-in banner glyph composition: faction sigil + hero monogram motif.</summary>
  public string CutInGlyph{get;private set;}
  /// <summary>Afterimage strike silhouettes emitted during Impact.</summary>
  public int AfterimageCount{get;private set;}
  /// <summary>Screen shake amplitude in reference pixels at 1080x1920.</summary>
  public float ShakeAmplitude{get;private set;}
  /// <summary>Finisher card line and recovery flourish.</summary>
  public string FinisherLine{get;private set;}
  public string RecoveryMotif{get;private set;}

  public UltimateImpactBeat[] ImpactBeats{get;private set;}
  public UltimateEnvironmentCue[] EnvironmentCues{get;private set;}
  public UltimatePhase[] PhaseOrder{get;private set;}

  /// <summary>Presentation-only duration scale: heavier signatures linger longer. Speed toggle still applies.</summary>
  public float PhaseDuration(UltimatePhase phase){
   switch(phase){
    case UltimatePhase.Anticipation: return 0.42f;
    case UltimatePhase.CutIn: return 0.58f;
    case UltimatePhase.TimeDilation: return Clamp(FreezeSeconds,0.1f,0.9f);
    case UltimatePhase.Impact: return 0.55f+ImpactBeats.Length*0.09f;
    case UltimatePhase.EnvironmentResponse: return 0.44f;
    case UltimatePhase.Finisher: return 0.62f;
    case UltimatePhase.Recovery: return 0.30f;
    default: return 0.4f;
   }
  }
  static float Clamp(float v,float min,float max){return v<min?min:(v>max?max:v);}

  public UltimatePresentation(
   HeroDefinition hero,HeroDestiny destiny,SkillDefinition ultimate,
   string signatureName,string signatureLine,string systemAlert,string fateFragment,
   UltimateCameraMove camera,UltimateTimeScale timeScale,float freezeSeconds,
   int afterimages,float shakeAmplitude,string finisherLine,string recoveryMotif,
   UltimateImpactBeat[] impactBeats,UltimateEnvironmentCue[] environmentCues){
   if(hero==null)throw new ArgumentNullException("hero");
   if(ultimate==null)throw new ArgumentNullException("ultimate");
   HeroId=hero.Id;Hero=hero;Destiny=destiny;
   FactionToken=AwakenedRealmsVisualTheme.Faction(hero.Faction);
   RarityToken=AwakenedRealmsVisualTheme.Rarity(hero.Rarity);
   UltimateSkill=ultimate;
   SignatureName=signatureName;SignatureLine=signatureLine;SystemAlert=systemAlert;FateFragment=fateFragment;
   CameraMove=camera;TimeScale=timeScale;FreezeSeconds=freezeSeconds;
   CutInGlyph=FactionToken.Sigil+" "+hero.Name.Substring(0,1).ToUpperInvariant()+" "+FactionToken.Sigil;
   AfterimageCount=afterimages;ShakeAmplitude=shakeAmplitude;
   FinisherLine=finisherLine;RecoveryMotif=recoveryMotif;
   ImpactBeats=impactBeats;EnvironmentCues=environmentCues;
   PhaseOrder=new[]{UltimatePhase.Anticipation,UltimatePhase.CutIn,UltimatePhase.TimeDilation,UltimatePhase.Impact,UltimatePhase.EnvironmentResponse,UltimatePhase.Finisher,UltimatePhase.Recovery};
  }
 }

 /// <summary>Data-driven catalog: one exaggerated anime-scale set piece per hero, each anchored to
 /// HeroDestiny (first-timeline title/fate), FactionVisualToken (sigil/motto/colors), SkillCatalog
 /// ultimate name, and Echo/Realm system language. Presentation only; never authoritative.</summary>
 public static class AwakenedRealmsUltimatePresentation {
  static UltimateImpactBeat IB(string id,string motion,int hits,float delay){return new UltimateImpactBeat(id,motion,hits,delay);}
  static UltimateEnvironmentCue EC(string hook,float intensity){return new UltimateEnvironmentCue(hook,intensity);}

  static UltimatePresentation U(string heroId,
   string signatureName,string signatureLine,string systemAlert,string fateFragment,
   UltimateCameraMove camera,UltimateTimeScale timeScale,float freeze,
   int afterimages,float shake,string finisher,string recovery,
   UltimateImpactBeat[] beats,UltimateEnvironmentCue[] cues){
   var hero=HeroCatalog.Get(heroId);
   if(hero==null)throw new ArgumentException("Unknown hero: "+heroId);
   var ultimate=SkillCatalog.ForHero(heroId).FirstOrDefault(x=>x.Kind==SkillKind.Ultimate);
   if(ultimate==null)throw new ArgumentException("Hero has no ultimate skill: "+heroId);
   return new UltimatePresentation(hero,AwakenedRealmsNarrative.ForHero(heroId),ultimate,
    signatureName,signatureLine,systemAlert,fateFragment,camera,timeScale,freeze,
    afterimages,shake,finisher,recovery,beats,cues);
  }

  public static readonly UltimatePresentation[] All={
   U("cinder",
    "PHOENIX WARDEN: GATE OF EMBERS","The ash remembers the fire -- she stands where the gate once fell.",
    "[ECHO MEMORY TRANSFER: IRREVERSIBLE]","Died holding the capital gate during the first Realm Collapse.",
    UltimateCameraMove.CraneRise,UltimateTimeScale.NearStop,0.72f,6,14f,
    "The gate holds this time.","Ember wings fold back into a single standing silhouette.",
    new[]{IB("wing_arc","Searing wing arc",3,0.00f),IB("gate_pillar","Pillar of emberglass erupts",1,0.18f),IB("rebirth_flash","Rebirth flash detonation",1,0.34f)},
    new[]{EC("sky_ignition",0.9f),EC("ash_fall",0.7f),EC("emberglass_bloom",0.8f)}),
   U("brasa",
    "ASHEN BASTION: CRATER OATH","The nameless guard plants the banner no army breaks.",
    "[NEW FACTION REGISTERED: ECHOBOUND]","Died nameless in a dungeon before his defensive talent was recognized.",
    UltimateCameraMove.PushIn,UltimateTimeScale.Slow,0.38f,2,10f,
    "The line holds.","Settles into a cratered stance; the banner keeps burning.",
    new[]{IB("shield_slam","Shield slam crater",1,0.00f),IB("bulwark_wave","Molten bulwark shockwave",2,0.16f)},
    new[]{EC("ground_crater",0.8f),EC("banner_ember",0.6f),EC("ash_wall",0.5f)}),
   U("mistral",
    "HORIZON SPEAR: DROWNED SKY VOLLEY","The drowned horizon still sings -- one arrow answers for the harbor.",
    "[HISTORICAL EVENT ADVANCED]","Became the Tide Realm's greatest ranger after losing her home.",
    UltimateCameraMove.TrackingShot,UltimateTimeScale.NearStop,0.60f,5,9f,
    "The sea misses nothing.","Bowstring hum fades; tidewater recedes from the lens.",
    new[]{IB("tide_draw","Tide-dragged nock",1,0.00f),IB("horizon_pierce","Horizon-piercing lance",1,0.20f),IB("undertow_hits","Undertow ricochet volley",4,0.30f)},
    new[]{EC("tidal_lens",0.85f),EC("rain_reversal",0.7f),EC("harbor_light",0.6f)}),
   U("maris",
    "MOON-TIDE SAINT: CLINIC OF TIDES","Moonlight triages the field; the vanished healer was never lost.",
    "[ECHO RESONANCE DETECTED]","Vanished while investigating illegal healing experiments.",
    UltimateCameraMove.OverheadSeal,UltimateTimeScale.Slow,0.40f,3,6f,
    "No name is forgotten here.","Moonlit rings settle; allies' silhouettes steady.",
    new[]{IB("moon_seal","Moon seal descends",1,0.00f),IB("tide_surge","Restorative undertow burst",3,0.18f),IB("pressure_wave","Crushing tide pressure",1,0.30f)},
    new[]{EC("moonwell",0.8f),EC("healing_rain",0.7f),EC("undertow_dark",0.5f)}),
   U("briar",
    "WORLDROOT GUARDIAN: SECOND MEMORY","Every root keeps a second memory -- the forest answers in kind.",
    "[REALM DEFENSE RESPONSE ACTIVE]","Awakened only after the Verdant Realm was nearly destroyed.",
    UltimateCameraMove.CraneRise,UltimateTimeScale.Still,0.30f,3,12f,
    "The colossus remembers you.","Roots sheath back into bark; the grove exhales.",
    new[]{IB("root_quake","Worldroot upheaval",2,0.00f),IB("colossus_fist","Colossus fist descent",1,0.22f),IB("canopy_crush","Canopy crush wave",2,0.36f)},
    new[]{EC("root_lattice",0.9f),EC("pollen_glow",0.6f),EC("forest_breath",0.7f)}),
   U("fern",
    "THORN WITCH: RED SKY VERDICT","She dreamed this sky once. This time it answers her.",
    "[CAUSAL INCONSISTENCY ESCALATED]","Executed as a heretic after predicting disasters nobody believed.",
    UltimateCameraMove.WhipPan,UltimateTimeScale.NearStop,0.66f,5,11f,
    "The dream was evidence.","Spores scatter; the red horizon drains back to night.",
    new[]{IB("hex_bloom","Bloom hex eruption",4,0.00f),IB("thorn_cage","Thorn cage collapse",3,0.20f),IB("verdict_nova","Verdant nova verdict",1,0.38f)},
    new[]{EC("red_sky",0.95f),EC("spore_storm",0.8f),EC("dream_static",0.6f)}),
   U("solenne",
    "SUN-CROWNED HERETIC: ALTAR INFERNO","The halo was forged; the light is hers -- the altar burns first.",
    "[DESTINY BRANCH FORMED]","Began as a saint and ended as the church's greatest enemy.",
    UltimateCameraMove.ZoomSnap,UltimateTimeScale.NearStop,0.70f,6,13f,
    "Faith is not a prison.","Solar crown dims to a single ember halo.",
    new[]{IB("halo_ignition","Halo ignition ring",2,0.00f),IB("prism_verdict","Prism verdict lance",3,0.18f),IB("crown_supernova","Solar crown supernova",1,0.36f)},
    new[]{EC("corona_flare",0.9f),EC("burning_records",0.75f),EC("stained_light",0.6f)}),
   U("lux",
    "LAST BEACON: THREADLIGHT LANTERN","He sees the threads nobody else can -- and ties them into dawn.",
    "[AUTHORITY VISIBILITY ANOMALY]","Died before graduation and became a footnote in another hero's biography.",
    UltimateCameraMove.OverheadSeal,UltimateTimeScale.Slow,0.42f,4,7f,
    "The footnote becomes the beacon.","Lantern threads dim; allied auras linger.",
    new[]{IB("thread_weave","Echo thread weave",3,0.00f),IB("beacon_pulse","Sanctuary pulse ring",2,0.20f),IB("lantern_flare","Lantern flare burst",1,0.34f)},
    new[]{EC("thread_lattice",0.85f),EC("lantern_glow",0.8f),EC("dawn_horizon",0.5f)}),
   U("nyx",
    "BLACK COMET: SISTER'S VOW","The eclipse favors the patient -- the contract dies with her target.",
    "[LEGENDARY DESTINY NEGOTIATION]","Became an assassin queen after her sister's murder.",
    UltimateCameraMove.WhipPan,UltimateTimeScale.NearStop,0.78f,8,15f,
    "No more debts in blood.","Comet trail gutters out; only the afterimage stands.",
    new[]{IB("comet_entry","Comet entry dash",1,0.00f),IB("eclipse_cross","Eclipse cross slashes",6,0.14f),IB("umbral_collapse","Umbral collapse detonation",1,0.40f)},
    new[]{EC("eclipse_corona",0.9f),EC("night_rain",0.7f),EC("contract_burn",0.6f)}),
   U("vesper",
    "ECLIPSE BLADE: FAMILIAR SWORD","A fighting style only the dead should know -- rewritten for the living.",
    "[FUTURE DIVERGENCE: 37.4%]","Survived every guild war and vanished after the final breach.",
    UltimateCameraMove.OrbitSlash,UltimateTimeScale.NearStop,0.62f,7,11f,
    "The eclipse cuts both ways.","Afterimages snap back into one blade.",
    new[]{IB("dusk_open","Dusk opener slash",2,0.00f),IB("eclipse_dance","Eclipse dance flurry",5,0.16f),IB("breach_cut","Final breach cut",1,0.38f)},
    new[]{EC("moon_occlusion",0.8f),EC("afterimage_smear",0.85f),EC("guild_silence",0.5f)}),
   U("pippin",
    "FORTUNE GARDENER: WORLDSEED FESTIVAL","A worthless seed, a continental bloom -- luck refuses the script.",
    "[FUTURE RELIC SECURED]","Never became famous but accidentally saved millions.",
    UltimateCameraMove.PushIn,UltimateTimeScale.Slow,0.34f,4,8f,
    "The harmless choice saves everyone.","Petals drift down; the field smells like harvest.",
    new[]{IB("seed_burst","Worldseed germination",2,0.00f),IB("festival_bloom","Festival bloom barrage",5,0.18f),IB("fortune_shower","Golden fortune shower",3,0.34f)},
    new[]{EC("petal_storm",0.85f),EC("golden_luck",0.7f),EC("worldseed_glow",0.6f)}),
   U("tavi",
    "REDLINE PRODIGY: OUTRUN THE COLLAPSE","The first person to outrun a collapsing Realm boundary.",
    "[FUTURE DIVERGENCE: 51.2%]","Died young chasing academy rank records.",
    UltimateCameraMove.TrackingShot,UltimateTimeScale.NearStop,0.80f,9,10f,
    "Rank zero laps the apocalypse.","Speed lines fade; a single footprint glows behind the blast.",
    new[]{IB("redline_dash","Redline dash strike",2,0.00f),IB("salvo_stream","Redline salvo stream",7,0.12f),IB("boundary_break","Boundary-breaking kick",1,0.40f)},
    new[]{EC("speed_lines",0.9f),EC("horizon_smear",0.8f),EC("rank_zero_spark",0.5f)}),
  };

  static readonly Dictionary<string,UltimatePresentation> ByHero=All.ToDictionary(x=>x.HeroId);

  public static UltimatePresentation ForHero(string heroId){
   UltimatePresentation p;
   return heroId!=null&&ByHero.TryGetValue(heroId,out p)?p:null;
  }
  public static UltimatePresentation ForHeroName(string name){
   var hero=HeroCatalog.All.FirstOrDefault(x=>string.Equals(x.Name,name,StringComparison.OrdinalIgnoreCase));
   return hero==null?null:ForHero(hero.Id);
  }
 }
}
