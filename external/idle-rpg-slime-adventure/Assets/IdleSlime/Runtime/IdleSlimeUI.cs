using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using IdleSlime.Core;
using UnityEngine;
using UnityEngine.UI;

namespace IdleSlime.Runtime {
public sealed class IdleSlimeUI : MonoBehaviour {
 enum View{Home,Heroes,HeroDetail,Formation,Campaign,Summon,Battle,Result}
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

 IdleSlimeSession s; RectTransform content; Text stats; BattleResult result; string summonText; string detailHeroId;
 Coroutine battleRoutine; BattlePresentationPlan battlePlan; float battleSpeed=1f; Image allyHpFill,enemyHpFill; Text battleStatus,speedLabel;
 readonly Dictionary<string,Image> heroEnergy=new Dictionary<string,Image>();
 readonly Dictionary<string,RectTransform> heroCards=new Dictionary<string,RectTransform>();
 AwakenedRealmsPremiumMotion Motion{get{return AwakenedRealmsPremiumMotion.Instance;}}

 public void Initialize(IdleSlimeSession session){s=session;var _=Motion;BuildShell();Show(View.Home);}

 void BuildShell(){
  var c=GO("IdleSlimeCanvas",transform,typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));
  var canvas=c.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=5000;
  var scale=c.GetComponent<CanvasScaler>();scale.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;
  scale.referenceResolution=new Vector2(1080,1920);scale.matchWidthOrHeight=.5f;
  var root=Rect("Root",c.transform,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
  Image(root,C(AwakenedRealmsVisualTheme.VoidBase));
  PaintEchoField(root);
  var h=Rect("Header",root,new Vector2(0,1),new Vector2(1,1),new Vector2(24,-178),new Vector2(-24,-28));
  Panel(h,"echo_realm");
  var title=Text(h,"AWAKENED REALMS: IDLE RPG",38,TextAnchor.MiddleLeft,C(AwakenedRealmsVisualTheme.EchoCyan),FontStyle.Bold);
  Set(title.rectTransform,new Vector2(.04f,0),new Vector2(.5f,1),Vector2.zero,Vector2.zero);
  stats=Text(h,"",27,TextAnchor.MiddleRight,Color.white,FontStyle.Normal);
  Set(stats.rectTransform,new Vector2(.45f,0),new Vector2(.97f,1),Vector2.zero,Vector2.zero);
  content=Rect("Content",root,Vector2.zero,Vector2.one,new Vector2(24,178),new Vector2(-24,-196));
  var nav=Rect("Nav",root,new Vector2(0,0),new Vector2(1,0),new Vector2(24,24),new Vector2(-24,158));
  Panel(nav,"panel_base");
  string[] n={"HOME","HEROES","FORM","CAMPAIGN","SUMMON"};View[] v={View.Home,View.Heroes,View.Formation,View.Campaign,View.Summon};
  for(int i=0;i<5;i++){int j=i;var b=Button(nav,n[i],()=>Show(v[j]));Set(b.GetComponent<RectTransform>(),new Vector2(i/5f,0),new Vector2((i+1)/5f,1),new Vector2(6,10),new Vector2(-6,-10));}
 }

 // Realm-language backdrop: vignette wash + the arc's faction sigil rendered as a watermark.
 void PaintEchoField(RectTransform root){
  var beat=AwakenedRealmsNarrative.ForStage(s.HighestStage);
  var wash=Rect("EchoWash",root,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
  var wi=wash.gameObject.AddComponent<Image>();wi.color=C(AwakenedRealmsVisualTheme.EchoVeil);wi.raycastTarget=false;
  string glyph=EchoLanguage.EchoMark;
  if(beat!=null){var featured=HeroCatalog.Get(beat.FeaturedHeroId);if(featured!=null)glyph=AwakenedRealmsVisualTheme.Faction(featured.Faction).Sigil;}
  var sigil=Text(root,glyph,340,TextAnchor.MiddleCenter,C(AwakenedRealmsVisualTheme.EchoCyan,0.07f),FontStyle.Bold);
  Set(sigil.rectTransform,new Vector2(.35f,.30f),new Vector2(1f,.95f),Vector2.zero,Vector2.zero);
  sigil.raycastTarget=false;
 }

 void Show(View v){
  if(v!=View.Battle&&battleRoutine!=null){StopCoroutine(battleRoutine);battleRoutine=null;}
  Clear(content);Refresh();
  switch(v){case View.Home:Home();break;case View.Heroes:Heroes();break;case View.HeroDetail:HeroDetail();break;case View.Formation:Formation();break;case View.Campaign:Campaign();break;case View.Summon:Summon();break;case View.Battle:Battle();break;case View.Result:BattleResultView();break;}
 }
 void Refresh(){stats.text="GOLD  "+s.Gold.ToString("N0")+"\nGEMS  "+s.Gems.ToString("N0");}
 void Header(string a,string b){
  var t=Text(content,a,50,TextAnchor.UpperLeft,Color.white,FontStyle.Bold);Set(t.rectTransform,new Vector2(.04f,.88f),new Vector2(.96f,.99f),Vector2.zero,Vector2.zero);
  var q=Text(content,b,25,TextAnchor.UpperLeft,C(AwakenedRealmsVisualTheme.InkMuted),FontStyle.Normal);Set(q.rectTransform,new Vector2(.04f,.79f),new Vector2(.96f,.89f),Vector2.zero,Vector2.zero);
 }

 void Home(){
  var beat=AwakenedRealmsNarrative.ForStage(s.HighestStage);
  Header("ECHOBOUND COMMAND","Second life. New future. Every victory changes what comes next.");
  Card(0,.67f,.88f,"TEAM POWER",TeamPower().ToString("N0"),C(AwakenedRealmsVisualTheme.EchoCyan));
  Card(1,.44f,.64f,"CAMPAIGN","Stage "+s.HighestStage+" / "+CampaignCatalog.MaxStage+"  "+EchoLanguage.Divider+"  "+(beat==null?"Unwritten Future":beat.ArcTitle),C(AwakenedRealmsVisualTheme.SovereignGold));
  var st=CampaignCatalog.Stages[Mathf.Clamp(s.HighestStage-1,0,CampaignCatalog.MaxStage-1)];
  Card(2,.21f,.41f,beat==null?"NEXT ENEMY":beat.StageTitle,st.EnemyPower.ToString("N0")+" power",C(AwakenedRealmsVisualTheme.RealmSilver));
  var claim=Button(content,"CLAIM IDLE REWARDS",()=>{var r=s.ClaimIdle(DateTime.UtcNow);Debug.Log("[AwakenedRealms] idle +"+r.Gold+" gold +"+r.HeroXp+" xp");Show(View.Home);});
  Set(claim.GetComponent<RectTransform>(),new Vector2(.04f,.06f),new Vector2(.48f,.17f),Vector2.zero,Vector2.zero);
  var fight=Button(content,"ENTER THE NEXT ECHO",Fight);
  Set(fight.GetComponent<RectTransform>(),new Vector2(.52f,.06f),new Vector2(.96f,.17f),Vector2.zero,Vector2.zero);
  fight.GetComponent<Image>().color=C(AwakenedRealmsVisualTheme.SovereignGold);
 }

 void Heroes(){
  Header("ECHO ROSTER","These are not copies. Each contract binds a future that once ended differently.");
  float y=.75f;int order=0;
  foreach(var hs in s.Heroes.Values.OrderByDescending(x=>(int)HeroCatalog.Get(x.HeroId).Rarity).ThenBy(x=>x.HeroId)){
   var p=AwakenedRealmsVisualTheme.Presentation(hs.HeroId);var d=p.Definition;var hsState=hs;
   var row=Rect("Hero_"+d.Id,content,new Vector2(.05f,y-.105f),new Vector2(.95f,y),Vector2.zero,Vector2.zero);
   Panel(row,p.RarityToken.Rarity==HeroRarity.Legendary?"card_rarity":"card_standard");
   var rim=Rect("FactionRim",row,new Vector2(0,0),new Vector2(.014f,1f),Vector2.zero,Vector2.zero);
   Image(rim,C(p.FactionToken.Core));
   var sig=Text(row,p.FactionToken.Sigil,34,TextAnchor.MiddleCenter,C(p.FactionToken.Aura),FontStyle.Bold);Set(sig.rectTransform,new Vector2(.015f,.1f),new Vector2(.09f,.9f),Vector2.zero,Vector2.zero);
   var t=Text(row,d.Name.ToUpper()+"   "+new string('★',hsState.Stars)+"   "+p.RarityToken.EchoLabel+"\n"+p.FactionToken.DisplayName+" / "+d.Role+"   Lv."+hsState.Level+"   Power "+BattleSimulator.HeroPower(hsState).ToString("N0")+"\n"+p.BannerTitle,21,TextAnchor.MiddleLeft,Color.white,FontStyle.Normal);
   Set(t.rectTransform,new Vector2(.10f,0),new Vector2(.68f,1),Vector2.zero,Vector2.zero);
   string id=hsState.HeroId;int cost=Progression.GoldToLevel(hsState.Level);
   var b=Button(row,"AWAKEN\n"+cost+" G",()=>{if(s.Upgrade(id))Motion.Punch(row,MotionTokens.RarityPulseScale*2f,.22f);Show(View.Heroes);});
   Set(b.GetComponent<RectTransform>(),new Vector2(.70f,.15f),new Vector2(.855f,.85f),Vector2.zero,Vector2.zero);
   var info=Button(row,p.RarityToken.Crest,()=>{detailHeroId=id;Show(View.HeroDetail);});
   Set(info.GetComponent<RectTransform>(),new Vector2(.865f,.15f),new Vector2(.97f,.85f),Vector2.zero,Vector2.zero);
   info.GetComponent<Image>().color=C(p.RarityToken.Plate);info.GetComponentInChildren<Text>().color=C(p.RarityToken.Glow);
   heroCards[id]=row;Motion.Entrance(row,order,new Vector2(0,-24f));order++;y-=.118f;
  }
 }

 void HeroDetail(){
  var p=AwakenedRealmsVisualTheme.Presentation(detailHeroId);
  if(p==null){Show(View.Heroes);return;}
  var hs=s.Heroes[detailHeroId];var d=p.Definition;
  Header(d.Name.ToUpper(),p.BannerTitle);
  var stage=Rect("Banner",content,new Vector2(.05f,.46f),new Vector2(.95f,.76f),Vector2.zero,Vector2.zero);
  Panel(stage,"banner_hero");
  var sig=Text(stage,p.PortraitGlyph,190,TextAnchor.MiddleCenter,C(p.FactionToken.Core,0.22f),FontStyle.Bold);Set(sig.rectTransform,new Vector2(.40f,0),new Vector2(1f,1f),Vector2.zero,Vector2.zero);
  var mono=Text(stage,p.Monogram,150,TextAnchor.MiddleCenter,C(p.FactionToken.Core),FontStyle.Bold);Set(mono.rectTransform,new Vector2(0,.15f),new Vector2(.42f,.85f),Vector2.zero,Vector2.zero);
  var plate=Rect("RarityPlate",stage,new Vector2(.06f,.06f),new Vector2(.60f,.20f),Vector2.zero,Vector2.zero);
  Image(plate,C(p.RarityToken.Plate));
  var pr=Text(plate,new string('★',hs.Stars)+"  "+p.RarityToken.EchoLabel,24,TextAnchor.MiddleCenter,C(p.RarityToken.Glow),FontStyle.Bold);Set(pr.rectTransform,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
  var motto=Text(stage,"\""+p.FactionToken.Motto+"\"",22,TextAnchor.MiddleRight,C(p.FactionToken.Thread),FontStyle.Italic);Set(motto.rectTransform,new Vector2(.40f,.02f),new Vector2(.96f,.16f),Vector2.zero,Vector2.zero);
  var statsBlock=Text(content,"LV."+hs.Level+"   POWER "+BattleSimulator.HeroPower(hs).ToString("N0")+"   STARS "+hs.Stars+"/"+StarRules.MaxStars(d.Rarity)+"\n"+p.FactionToken.DisplayName+"  "+EchoLanguage.Divider+"  "+d.Role,26,TextAnchor.MiddleLeft,Color.white,FontStyle.Normal);
  Set(statsBlock.rectTransform,new Vector2(.06f,.37f),new Vector2(.94f,.45f),Vector2.zero,Vector2.zero);
  var destinyBlock=Text(content,p.Destiny==null?"":"FIRST TIMELINE: "+p.Destiny.FirstTimelineFate+"\n\n"+p.SignatureLine+"\n\n"+EchoLanguage.FractureMark+" "+p.Destiny.Secret,21,TextAnchor.UpperLeft,C(AwakenedRealmsVisualTheme.RealmSilver),FontStyle.Normal);
  Set(destinyBlock.rectTransform,new Vector2(.06f,.18f),new Vector2(.94f,.36f),Vector2.zero,Vector2.zero);
  var starUp=Button(content,StarUpLabel(detailHeroId),()=>{if(s.TryStarUp(detailHeroId))Motion.Punch(stage,MotionTokens.RarityPulseScale*3f,.30f);Show(View.HeroDetail);});
  Set(starUp.GetComponent<RectTransform>(),new Vector2(.08f,.04f),new Vector2(.46f,.14f),Vector2.zero,Vector2.zero);
  starUp.GetComponent<Image>().color=C(p.RarityToken.Plate);
  var back=Button(content,"BACK TO ROSTER",()=>Show(View.Heroes));Set(back.GetComponent<RectTransform>(),new Vector2(.54f,.04f),new Vector2(.92f,.14f),Vector2.zero,Vector2.zero);
  back.GetComponent<Image>().color=C(p.FactionToken.Core);
  Motion.RevealLayers(stage.GetComponentsInChildren<RectTransform>(true).Where(x=>x!=stage&&x.parent==stage).ToList());
 }

 void Formation(){
  Header("FORMATION","Two front slots, three back slots. Tap CHANGE after recruiting extras.");
  string[] pos={"FRONT 1","FRONT 2","BACK 1","BACK 2","BACK 3"};
  for(int i=0;i<5;i++){
   int slot=i;string id=s.Formation.Slots[i];var p=AwakenedRealmsVisualTheme.Presentation(id);var d=p.Definition;
   float y=.74f-i*.13f;
   var row=Rect("Slot",content,new Vector2(.05f,y-.10f),new Vector2(.95f,y),Vector2.zero,Vector2.zero);
   Panel(row,"card_standard");
   var rim=Rect("Rim",row,new Vector2(0,0),new Vector2(.014f,1f),Vector2.zero,Vector2.zero);Image(rim,C(p.FactionToken.Core));
   var t=Text(row,pos[i]+"   "+d.Name+"   "+Stars(p.RarityToken)+"\n"+p.FactionToken.DisplayName+" / "+d.Role+"   Lv."+s.Heroes[id].Level,25,TextAnchor.MiddleLeft,Color.white,FontStyle.Normal);
   Set(t.rectTransform,new Vector2(.04f,0),new Vector2(.70f,1),Vector2.zero,Vector2.zero);
   var b=Button(row,"CHANGE",()=>Cycle(slot));Set(b.GetComponent<RectTransform>(),new Vector2(.72f,.18f),new Vector2(.97f,.82f),Vector2.zero,Vector2.zero);
   Motion.Entrance(row,i,new Vector2(-24f,0));
  }
 }
 void Cycle(int slot){var owned=s.Heroes.Keys.OrderBy(x=>x).ToList();var cur=s.Formation.Slots.ToArray();int start=owned.IndexOf(cur[slot]);for(int n=1;n<=owned.Count;n++){string id=owned[(start+n)%owned.Count];if(cur.Contains(id))continue;cur[slot]=id;s.SetFormation(cur);break;}Show(View.Formation);}

 void Campaign(){
  var st=CampaignCatalog.Stages[Mathf.Clamp(s.HighestStage-1,0,CampaignCatalog.MaxStage-1)];
  var beat=AwakenedRealmsNarrative.ForStage(st.Number);
  Header(beat==null?"CAMPAIGN":beat.ArcTitle,beat==null?"Hands-free battles. Win to advance and collect rewards.":beat.ChapterTitle);
  Card(0,.61f,.79f,beat==null?"CURRENT STAGE":beat.StageTitle,"Stage "+st.Number+"  "+EchoLanguage.Divider+"  Enemy "+st.EnemyPower.ToString("N0"),C(AwakenedRealmsVisualTheme.SovereignGold));
  var story=Text(content,beat==null?"The future is unwritten.":beat.Summary,24,TextAnchor.UpperLeft,Color.white,FontStyle.Normal);Set(story.rectTransform,new Vector2(.06f,.38f),new Vector2(.94f,.60f),Vector2.zero,Vector2.zero);
  var sys=Text(content,beat==null?"":beat.SystemMessage,20,TextAnchor.MiddleCenter,C(AwakenedRealmsVisualTheme.EchoCyan),FontStyle.Bold);Set(sys.rectTransform,new Vector2(.06f,.31f),new Vector2(.94f,.38f),Vector2.zero,Vector2.zero);
  Card(1,.14f,.30f,"VICTORY REWARD",st.Gold+" Gold  "+EchoLanguage.Divider+"  "+st.HeroXp+" XP  "+EchoLanguage.Divider+"  "+st.Gems+" Gems",C(AwakenedRealmsVisualTheme.EchoCyan));
  var b=Button(content,"ENTER STORY BATTLE",Fight);Set(b.GetComponent<RectTransform>(),new Vector2(.18f,.02f),new Vector2(.82f,.10f),Vector2.zero,Vector2.zero);
  b.GetComponent<Image>().color=C(AwakenedRealmsVisualTheme.SovereignGold);
 }
 void Fight(){int index=Mathf.Clamp(s.HighestStage-1,0,CampaignCatalog.MaxStage-1);var stage=CampaignCatalog.Stages[index];result=s.Fight();battlePlan=BattlePresentationPlan.Build(s.Formation,s.Heroes,stage,result);Show(View.Battle);}

 void Battle(){
  heroEnergy.Clear();heroCards.Clear();
  Header("AUTO BATTLE","Stage "+battlePlan.StageNumber+"  "+EchoLanguage.Divider+"  deterministic combat presentation");
  var auto=Tag(content,"AUTO ON",C(AwakenedRealmsVisualTheme.EchoCyan));Set(auto,new Vector2(.05f,.745f),new Vector2(.23f,.79f),Vector2.zero,Vector2.zero);
  var speed=Button(content,"SPEED x"+battleSpeed.ToString("0"),()=>{battleSpeed=battleSpeed<2f?2f:1f;if(speedLabel!=null)speedLabel.text="SPEED x"+battleSpeed.ToString("0");});
  Set(speed.GetComponent<RectTransform>(),new Vector2(.76f,.735f),new Vector2(.95f,.795f),Vector2.zero,Vector2.zero);speed.GetComponent<Image>().color=C(AwakenedRealmsVisualTheme.PanelRaised);speedLabel=speed.GetComponentInChildren<Text>();

  var team=Rect("Allies",content,new Vector2(.04f,.49f),new Vector2(.48f,.72f),Vector2.zero,Vector2.zero);Panel(team,"panel_base");
  string[] slotLabel={"FRONT","FRONT","BACK","BACK","BACK"};
  for(int i=0;i<s.Formation.Slots.Length;i++){
   string id=s.Formation.Slots[i];var p=AwakenedRealmsVisualTheme.Presentation(id);var d=p.Definition;
   float x=(i%2)*.48f+.03f;float y=.69f-(i/2)*.31f;if(i>=4)x=.27f;
   var card=Rect("Hero_"+d.Name,team,new Vector2(x,y-.25f),new Vector2(x+.44f,y),Vector2.zero,Vector2.zero);
   Panel(card,p.RarityToken.Rarity==HeroRarity.Legendary?"card_rarity":"card_standard");
   var rim=Rect("Rim",card,new Vector2(0,.9f),new Vector2(1f,1f),Vector2.zero,Vector2.zero);Image(rim,C(p.FactionToken.Core));
   var name=Text(card,d.Name+" "+p.FactionToken.Sigil+"\n"+slotLabel[i],18,TextAnchor.UpperLeft,Color.white,FontStyle.Bold);Set(name.rectTransform,new Vector2(.05f,.38f),new Vector2(.95f,.94f),Vector2.zero,Vector2.zero);
   Bar(card,new Vector2(.05f,.24f),new Vector2(.95f,.34f),C(AwakenedRealmsVisualTheme.EchoCyan),1f);
   var en=Bar(card,new Vector2(.05f,.08f),new Vector2(.95f,.18f),C(AwakenedRealmsVisualTheme.EnergyThread),.18f);heroEnergy[d.Name]=en;heroCards[d.Name]=card;
  }
  var enemy=Rect("Enemy",content,new Vector2(.53f,.49f),new Vector2(.96f,.72f),Vector2.zero,Vector2.zero);Panel(enemy,"echo_realm");
  var enemyTitle=Text(enemy,battlePlan.EnemyName.ToUpper()+"\nSTAGE "+battlePlan.StageNumber,29,TextAnchor.MiddleCenter,C(AwakenedRealmsVisualTheme.CollapseRed),FontStyle.Bold);Set(enemyTitle.rectTransform,new Vector2(.05f,.36f),new Vector2(.95f,.92f),Vector2.zero,Vector2.zero);
  enemyHpFill=Bar(enemy,new Vector2(.08f,.16f),new Vector2(.92f,.28f),C(AwakenedRealmsVisualTheme.CollapseRed),1f);

  var teamHp=Rect("TeamHPPanel",content,new Vector2(.05f,.42f),new Vector2(.48f,.475f),Vector2.zero,Vector2.zero);Panel(teamHp,"panel_base");
  var th=Text(teamHp,"TEAM HP",17,TextAnchor.MiddleLeft,C(AwakenedRealmsVisualTheme.InkMuted),FontStyle.Bold);Set(th.rectTransform,new Vector2(.03f,.35f),new Vector2(.30f,.95f),Vector2.zero,Vector2.zero);
  allyHpFill=Bar(teamHp,new Vector2(.31f,.30f),new Vector2(.96f,.70f),C(AwakenedRealmsVisualTheme.EchoCyan),1f);

  battleStatus=Text(content,"Engaging "+battlePlan.EnemyName+"...",31,TextAnchor.MiddleCenter,Color.white,FontStyle.Bold);Set(battleStatus.rectTransform,new Vector2(.06f,.24f),new Vector2(.94f,.40f),Vector2.zero,Vector2.zero);
  var hint=Text(content,"ENERGY builds with normal attacks  "+EchoLanguage.Divider+"  skills consume energy",20,TextAnchor.MiddleCenter,C(AwakenedRealmsVisualTheme.InkMuted),FontStyle.Normal);Set(hint.rectTransform,new Vector2(.06f,.17f),new Vector2(.94f,.24f),Vector2.zero,Vector2.zero);
  battleRoutine=StartCoroutine(RunBattle());
 }

 IEnumerator RunBattle(){
  float allyHp=1f,enemyHp=1f;
  var energyState=new Dictionary<string,float>();
  foreach(string name in heroEnergy.Keys)energyState[name]=.18f;
  for(int i=0;i<battlePlan.Beats.Count;i++){
   var beat=battlePlan.Beats[i];
   if(beat.AllyTurn){
    enemyHp=Mathf.Clamp01(enemyHp-beat.DamagePercent/100f);enemyHpFill.fillAmount=enemyHp;
    Image e;
    if(heroEnergy.TryGetValue(beat.ActorName,out e)){float next=beat.Skill?0f:Mathf.Min(1f,energyState[beat.ActorName]+.30f);energyState[beat.ActorName]=next;e.fillAmount=next;}
    RectTransform card;if(heroCards.TryGetValue(beat.ActorName,out card))Motion.Punch(card,beat.Skill?.14f:.06f,.22f);
    battleStatus.text=beat.ActorName+(beat.Skill?" unleashes ULTIMATE":" attacks")+"  "+EchoLanguage.Divider+"  "+Mathf.RoundToInt(beat.DamagePercent)+"% DAMAGE";
    battleStatus.color=beat.Skill?C(AwakenedRealmsVisualTheme.SovereignGold):Color.white;
   }else{
    allyHp=Mathf.Clamp01(allyHp-beat.DamagePercent/100f);allyHpFill.fillAmount=allyHp;
    if(enemyHpFill!=null&&enemyHpFill.transform.parent!=null)Motion.Shake((RectTransform)enemyHpFill.transform.parent.parent,6f,.18f);
    battleStatus.text=beat.ActorName+(beat.Skill?" uses OVERDRIVE":" strikes the formation")+"  "+EchoLanguage.Divider+"  "+Mathf.RoundToInt(beat.DamagePercent)+"% DAMAGE";
    battleStatus.color=C(AwakenedRealmsVisualTheme.CollapseRed);
   }
   DamagePopup(beat.AllyTurn?new Vector2(.74f,.47f):new Vector2(.26f,.47f),"-"+Mathf.RoundToInt(beat.DamagePercent)+"%",beat.AllyTurn?C(AwakenedRealmsVisualTheme.SovereignGold):C(AwakenedRealmsVisualTheme.CollapseRed));
   yield return new WaitForSecondsRealtime(.46f/Mathf.Max(1f,battleSpeed));
  }
  battleStatus.text=battlePlan.Victory?"ENEMY DEFEATED  "+EchoLanguage.Divider+"  REWARDS SECURED":"FORMATION BROKEN  "+EchoLanguage.Divider+"  REGROUP";
  battleStatus.color=battlePlan.Victory?C(AwakenedRealmsVisualTheme.EchoCyan):C(AwakenedRealmsVisualTheme.CollapseRed);
  yield return new WaitForSecondsRealtime(.85f/Mathf.Max(1f,battleSpeed));
  battleRoutine=null;Show(View.Result);
 }

 void DamagePopup(Vector2 anchor,string value,Color color){
  var t=Text(content,value,38,TextAnchor.MiddleCenter,color,FontStyle.Bold);
  var rt=t.rectTransform;Set(rt,anchor-new Vector2(.11f,.025f),anchor+new Vector2(.11f,.035f),Vector2.zero,Vector2.zero);
  float dur=.52f/Mathf.Max(1f,battleSpeed);
  Motion.Popup(rt,rt.anchoredPosition,rt.anchoredPosition+new Vector2(0,MotionTokens.DamagePopupRisePx),dur,()=>{if(t!=null)Destroy(t.gameObject);});
 }

 void BattleResultView(){
  bool win=result!=null&&result.Victory;
  Header(win?"VICTORY":"DEFEAT",win?"Rewards secured. Continue pushing.":"Level heroes or adjust formation.");
  var x=Text(content,win?EchoLanguage.SovereignMark+"  VICTORY":EchoLanguage.FractureMark+"  DEFEAT",80,TextAnchor.MiddleCenter,win?C(AwakenedRealmsVisualTheme.EchoCyan):C(AwakenedRealmsVisualTheme.CollapseRed),FontStyle.Bold);Set(x.rectTransform,new Vector2(.05f,.57f),new Vector2(.95f,.82f),Vector2.zero,Vector2.zero);
  string rew=win?"+"+result.Gold+" Gold   +"+result.HeroXp+" XP   +"+result.Gems+" Gems":"No rewards";
  var q=Text(content,"Team "+result.TeamPower.ToString("N0")+" vs Enemy "+result.EnemyPower.ToString("N0")+"\n\n"+rew,30,TextAnchor.MiddleCenter,Color.white,FontStyle.Normal);Set(q.rectTransform,new Vector2(.08f,.29f),new Vector2(.92f,.56f),Vector2.zero,Vector2.zero);
  var b=Button(content,win?"CONTINUE TO STAGE "+s.HighestStage:"RETURN TO HEROES",()=>Show(win?View.Campaign:View.Heroes));Set(b.GetComponent<RectTransform>(),new Vector2(.17f,.10f),new Vector2(.83f,.22f),Vector2.zero,Vector2.zero);
  b.GetComponent<Image>().color=win?C(AwakenedRealmsVisualTheme.EchoCyan):C(AwakenedRealmsVisualTheme.SovereignGold);
  Motion.Pop(x.rectTransform,.3f,.5f);
 }

 void Summon(){
  Header("ECHO CONVERGENCE","Call an unrealized destiny across the fracture. The hero is real. The future is not fixed.");
  var star=Text(content,EchoLanguage.ResonanceMark,150,TextAnchor.MiddleCenter,C(AwakenedRealmsVisualTheme.SovereignGold),FontStyle.Bold);Set(star.rectTransform,new Vector2(.3f,.59f),new Vector2(.7f,.82f),Vector2.zero,Vector2.zero);
  var info=Text(content,summonText??"Legendary 3%   "+EchoLanguage.Divider+"   Epic 22%   "+EchoLanguage.Divider+"   Rare 75%\nSOVEREIGN OF ECHOES",27,TextAnchor.MiddleCenter,Color.white,FontStyle.Normal);Set(info.rectTransform,new Vector2(.08f,.37f),new Vector2(.92f,.58f),Vector2.zero,Vector2.zero);
  var b=Button(content,"BIND ECHO x1   "+EchoLanguage.Divider+"   300 GEMS",()=>{
   var h=s.Summon(new SeededRandom(Environment.TickCount));
   if(h==null)summonText="Not enough Gems.";
   else{var p=AwakenedRealmsVisualTheme.Presentation(h.Id);summonText=p.RarityToken.EchoLabel+"  "+EchoLanguage.Divider+"  "+h.Name+"\n"+p.FactionToken.DisplayName+" / "+h.Role+(p.Destiny==null?"":"\nFUTURE TITLE: "+p.Destiny.FirstTimelineTitle);Motion.Pop(star.rectTransform,p.RarityToken.PulseScale*8f,.5f);}
   Show(View.Summon);
  });
  Set(b.GetComponent<RectTransform>(),new Vector2(.18f,.19f),new Vector2(.82f,.32f),Vector2.zero,Vector2.zero);
  b.GetComponent<Image>().color=C(AwakenedRealmsVisualTheme.SovereignGold);
  var own=Text(content,"Bound echoes  "+s.Heroes.Count+" / "+HeroCatalog.All.Length,24,TextAnchor.MiddleCenter,C(AwakenedRealmsVisualTheme.InkMuted),FontStyle.Normal);Set(own.rectTransform,new Vector2(.2f,.08f),new Vector2(.8f,.15f),Vector2.zero,Vector2.zero);
 }

 int TeamPower(){int p=0;foreach(string id in s.Formation.Slots)p+=BattleSimulator.HeroPower(s.Heroes[id]);return p;}
 string StarUpLabel(string heroId){
  HeroState hs;
  if(!s.Heroes.TryGetValue(heroId,out hs))return "STAR UP";
  var d=HeroCatalog.Get(heroId);
  if(d==null)return "STAR UP";
  if(StarRules.IsMaxed(d.Rarity,hs.Stars))return "MAX STARS\n"+hs.Stars+"★";
  var r=StarRules.Requirement(d.Rarity,hs.Stars);
  if(r==null)return "STAR UP";
  return "STAR UP  "+hs.Stars+"→"+(hs.Stars+1)+"★\n"+r.SameHeroCopies+" COPY  +  "+r.FodderCount+"x "+r.FodderStars+"★ "+r.FodderRarity+" FODDER";
 }
 static string Stars(RarityVisualToken r){return new string('★',r.StarCount);}
 void Card(int order,float ymin,float ymax,string a,string b,Color c){
  var r=Rect(a,content,new Vector2(.05f,ymin),new Vector2(.95f,ymax),Vector2.zero,Vector2.zero);Panel(r,"card_standard");
  var x=Text(r,a,22,TextAnchor.UpperLeft,C(AwakenedRealmsVisualTheme.InkMuted),FontStyle.Bold);Set(x.rectTransform,new Vector2(.04f,.54f),new Vector2(.96f,.92f),Vector2.zero,Vector2.zero);
  var y=Text(r,b,37,TextAnchor.LowerLeft,c,FontStyle.Bold);Set(y.rectTransform,new Vector2(.04f,.08f),new Vector2(.96f,.58f),Vector2.zero,Vector2.zero);
  Motion.Entrance(r,order,new Vector2(0,-18f));
 }

 // Layered panel rendering: each PanelStyle layer becomes an inset child Image so
 // a later art pass (or DOTween reveal) can restyle/animate layers independently.
 static void Panel(RectTransform r,string styleKey){
  var style=AwakenedRealmsVisualTheme.Style(styleKey);
  if(style==null){Image(r,C(AwakenedRealmsVisualTheme.Panel));return;}
  bool first=true;
  foreach(var layer in style.Layers){
   RectTransform lr=first?r:Rect("Layer_"+layer.Key,r,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);
   if(!first)Set(lr,Vector2.zero,Vector2.one,new Vector2(layer.InsetPixels,layer.InsetPixels),new Vector2(-layer.InsetPixels,-layer.InsetPixels));
   var img=lr.gameObject.GetComponent<Image>()??lr.gameObject.AddComponent<Image>();
   img.color=C(layer.Color);img.raycastTarget=first; // only the base layer participates in raycasts
   first=false;
  }
 }
 static RectTransform Tag(Transform p,string value,Color color){var r=Rect("Tag",p,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);Image(r,new Color(color.r*.35f,color.g*.35f,color.b*.35f,1));var t=Text(r,value,18,TextAnchor.MiddleCenter,color,FontStyle.Bold);Set(t.rectTransform,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);return r;}
 static Image Bar(Transform p,Vector2 amin,Vector2 amax,Color fillColor,float value){var bg=Rect("Bar",p,amin,amax,Vector2.zero,Vector2.zero);Image(bg,C(AwakenedRealmsVisualTheme.BannerInk));var fr=Rect("Fill",bg,Vector2.zero,Vector2.one,new Vector2(3,3),new Vector2(-3,-3));var fi=fr.gameObject.AddComponent<Image>();fi.color=fillColor;fi.type=UnityEngine.UI.Image.Type.Filled;fi.fillMethod=UnityEngine.UI.Image.FillMethod.Horizontal;fi.fillOrigin=0;fi.fillAmount=Mathf.Clamp01(value);return fi;}
 static GameObject GO(string n,Transform p,params Type[] t){var g=new GameObject(n,t);g.transform.SetParent(p,false);return g;}
 static RectTransform Rect(string n,Transform p,Vector2 amin,Vector2 amax,Vector2 omin,Vector2 omax){var g=GO(n,p,typeof(RectTransform));var r=(RectTransform)g.transform;Set(r,amin,amax,omin,omax);return r;}
 static void Set(RectTransform r,Vector2 amin,Vector2 amax,Vector2 omin,Vector2 omax){r.anchorMin=amin;r.anchorMax=amax;r.offsetMin=omin;r.offsetMax=omax;}
 static void Image(RectTransform r,Color c){var i=r.gameObject.GetComponent<Image>()??r.gameObject.AddComponent<Image>();i.color=c;}
 static Text Text(Transform p,string v,int size,TextAnchor a,Color c,FontStyle s){var g=GO("Text",p,typeof(RectTransform),typeof(Text));var t=g.GetComponent<Text>();t.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");if(t.font==null)t.font=Resources.GetBuiltinResource<Font>("Arial.ttf");t.text=v;t.fontSize=size;t.alignment=a;t.color=c;t.fontStyle=s;t.horizontalOverflow=HorizontalWrapMode.Wrap;t.verticalOverflow=VerticalWrapMode.Overflow;return t;}
 static Button Button(Transform p,string label,Action action){var g=GO("Button",p,typeof(RectTransform),typeof(Image),typeof(Button));g.GetComponent<Image>().color=C(AwakenedRealmsVisualTheme.PanelRaised);var b=g.GetComponent<Button>();b.onClick.AddListener(()=>action());var t=Text(g.transform,label,23,TextAnchor.MiddleCenter,Color.white,FontStyle.Bold);Set(t.rectTransform,Vector2.zero,Vector2.one,new Vector2(6,4),new Vector2(-6,-4));return b;}
 static void Clear(Transform t){for(int i=t.childCount-1;i>=0;i--)Destroy(t.GetChild(i).gameObject);}
}
}
