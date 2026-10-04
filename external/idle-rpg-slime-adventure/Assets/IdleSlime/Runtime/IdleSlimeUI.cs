using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using IdleSlime.Core;
using UnityEngine;
using UnityEngine.UI;

namespace IdleSlime.Runtime {
public sealed class IdleSlimeUI : MonoBehaviour {
 enum View{Home,Heroes,Formation,Campaign,Summon,Battle,Result}
 static readonly Color Bg=new Color(.055f,.07f,.12f,.99f),Panel=new Color(.10f,.13f,.21f,.99f),Accent=new Color(.40f,.86f,.72f,1),Orange=new Color(.98f,.66f,.30f,1),Muted=new Color(.66f,.71f,.80f,1),Danger=new Color(.95f,.35f,.38f,1),Energy=new Color(.48f,.70f,1f,1);
 IdleSlimeSession s; RectTransform content; Text stats; BattleResult result; string summonText;
 Coroutine battleRoutine; BattlePresentationPlan battlePlan; float battleSpeed=1f; Image allyHpFill,enemyHpFill; Text battleStatus,speedLabel;
 readonly Dictionary<string,Image> heroEnergy=new Dictionary<string,Image>();

 public void Initialize(IdleSlimeSession session){s=session;BuildShell();Show(View.Home);}
 void BuildShell(){var c=GO("IdleSlimeCanvas",transform,typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));var canvas=c.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=5000;var scale=c.GetComponent<CanvasScaler>();scale.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scale.referenceResolution=new Vector2(1080,1920);scale.matchWidthOrHeight=.5f;var root=Rect("Root",c.transform,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);Image(root,Bg);var h=Rect("Header",root,new Vector2(0,1),new Vector2(1,1),new Vector2(24,-178),new Vector2(-24,-28));Image(h,Panel);var title=Text(h,"AWAKENED REALMS: IDLE RPG",38,TextAnchor.MiddleLeft,Accent,FontStyle.Bold);Set(title.rectTransform,new Vector2(.03f,0),new Vector2(.5f,1),Vector2.zero,Vector2.zero);stats=Text(h,"",27,TextAnchor.MiddleRight,Color.white,FontStyle.Normal);Set(stats.rectTransform,new Vector2(.45f,0),new Vector2(.97f,1),Vector2.zero,Vector2.zero);content=Rect("Content",root,Vector2.zero,Vector2.one,new Vector2(24,178),new Vector2(-24,-196));var nav=Rect("Nav",root,new Vector2(0,0),new Vector2(1,0),new Vector2(24,24),new Vector2(-24,158));Image(nav,Panel);string[] n={"HOME","HEROES","FORM","CAMPAIGN","SUMMON"};View[] v={View.Home,View.Heroes,View.Formation,View.Campaign,View.Summon};for(int i=0;i<5;i++){int j=i;var b=Button(nav,n[i],()=>Show(v[j]));Set(b.GetComponent<RectTransform>(),new Vector2(i/5f,0),new Vector2((i+1)/5f,1),new Vector2(6,10),new Vector2(-6,-10));}}
 void Show(View v){if(v!=View.Battle&&battleRoutine!=null){StopCoroutine(battleRoutine);battleRoutine=null;}Clear(content);Refresh();switch(v){case View.Home:Home();break;case View.Heroes:Heroes();break;case View.Formation:Formation();break;case View.Campaign:Campaign();break;case View.Summon:Summon();break;case View.Battle:Battle();break;case View.Result:BattleResultView();break;}}
 void Refresh(){stats.text="GOLD  "+s.Gold.ToString("N0")+"\nGEMS  "+s.Gems.ToString("N0");}
 void Header(string a,string b){var t=Text(content,a,50,TextAnchor.UpperLeft,Color.white,FontStyle.Bold);Set(t.rectTransform,new Vector2(.04f,.88f),new Vector2(.96f,.99f),Vector2.zero,Vector2.zero);var q=Text(content,b,25,TextAnchor.UpperLeft,Muted,FontStyle.Normal);Set(q.rectTransform,new Vector2(.04f,.79f),new Vector2(.96f,.89f),Vector2.zero,Vector2.zero);}
 void Home(){Header("COMMAND DECK","Build your squad, collect idle rewards, then push the campaign.");Card(.67f,.88f,"TEAM POWER",TeamPower().ToString("N0"),Accent);Card(.44f,.64f,"CAMPAIGN","Stage "+s.HighestStage+" / 20",Orange);var st=CampaignCatalog.Stages[Mathf.Clamp(s.HighestStage-1,0,19)];Card(.21f,.41f,"NEXT ENEMY",st.EnemyPower.ToString("N0")+" power",Muted);var claim=Button(content,"CLAIM IDLE REWARDS",()=>{var r=s.ClaimIdle(DateTime.UtcNow);Debug.Log("[AwakenedRealms] idle +"+r.Gold+" gold +"+r.HeroXp+" xp");Show(View.Home);});Set(claim.GetComponent<RectTransform>(),new Vector2(.04f,.06f),new Vector2(.48f,.17f),Vector2.zero,Vector2.zero);var fight=Button(content,"AUTO BATTLE",Fight);Set(fight.GetComponent<RectTransform>(),new Vector2(.52f,.06f),new Vector2(.96f,.17f),Vector2.zero,Vector2.zero);fight.GetComponent<Image>().color=Orange;}
 void Heroes(){Header("HEROES","Owned roster. Level heroes with earned Gold.");float y=.75f;foreach(var hs in s.Heroes.Values.OrderByDescending(x=>(int)HeroCatalog.Get(x.HeroId).Rarity)){var d=HeroCatalog.Get(hs.HeroId);var row=Rect("Hero",content,new Vector2(.05f,y-.10f),new Vector2(.95f,y),Vector2.zero,Vector2.zero);Image(row,Panel);var t=Text(row,d.Name.ToUpper()+"   "+d.Rarity+"   "+d.Faction+" / "+d.Role+"\nLv."+hs.Level+"   Power "+BattleSimulator.HeroPower(hs).ToString("N0"),24,TextAnchor.MiddleLeft,Color.white,FontStyle.Normal);Set(t.rectTransform,new Vector2(.03f,0),new Vector2(.68f,1),Vector2.zero,Vector2.zero);string id=hs.HeroId;int cost=Progression.GoldToLevel(hs.Level);var b=Button(row,"LEVEL UP\n"+cost+" G",()=>{s.Upgrade(id);Show(View.Heroes);});Set(b.GetComponent<RectTransform>(),new Vector2(.70f,.15f),new Vector2(.97f,.85f),Vector2.zero,Vector2.zero);y-=.115f;}}
 void Formation(){Header("FORMATION","Two front slots, three back slots. Tap CHANGE after recruiting extras.");string[] pos={"FRONT 1","FRONT 2","BACK 1","BACK 2","BACK 3"};for(int i=0;i<5;i++){int slot=i;string id=s.Formation.Slots[i];var d=HeroCatalog.Get(id);float y=.74f-i*.13f;var row=Rect("Slot",content,new Vector2(.05f,y-.10f),new Vector2(.95f,y),Vector2.zero,Vector2.zero);Image(row,Panel);var t=Text(row,pos[i]+"   "+d.Name+"\n"+d.Faction+" / "+d.Role+"   Lv."+s.Heroes[id].Level,25,TextAnchor.MiddleLeft,Color.white,FontStyle.Normal);Set(t.rectTransform,new Vector2(.03f,0),new Vector2(.70f,1),Vector2.zero,Vector2.zero);var b=Button(row,"CHANGE",()=>Cycle(slot));Set(b.GetComponent<RectTransform>(),new Vector2(.72f,.18f),new Vector2(.97f,.82f),Vector2.zero,Vector2.zero);}}
 void Cycle(int slot){var owned=s.Heroes.Keys.OrderBy(x=>x).ToList();var cur=s.Formation.Slots.ToArray();int start=owned.IndexOf(cur[slot]);for(int n=1;n<=owned.Count;n++){string id=owned[(start+n)%owned.Count];if(cur.Contains(id))continue;cur[slot]=id;s.SetFormation(cur);break;}Show(View.Formation);}
 void Campaign(){Header("CAMPAIGN","Hands-free battles. Win to advance and collect rewards.");var st=CampaignCatalog.Stages[Mathf.Clamp(s.HighestStage-1,0,19)];Card(.58f,.82f,"CURRENT STAGE","Stage "+st.Number+"   Enemy "+st.EnemyPower.ToString("N0"),Orange);Card(.34f,.55f,"VICTORY REWARD",st.Gold+" Gold  •  "+st.HeroXp+" XP  •  "+st.Gems+" Gems",Accent);Card(.12f,.31f,"YOUR TEAM",TeamPower().ToString("N0")+" power",Muted);var b=Button(content,"START AUTO BATTLE",Fight);Set(b.GetComponent<RectTransform>(),new Vector2(.18f,.02f),new Vector2(.82f,.10f),Vector2.zero,Vector2.zero);b.GetComponent<Image>().color=Orange;}
 void Fight(){int index=Mathf.Clamp(s.HighestStage-1,0,19);var stage=CampaignCatalog.Stages[index];result=s.Fight();battlePlan=BattlePresentationPlan.Build(s.Formation,s.Heroes,stage,result);Show(View.Battle);}

 void Battle(){
  heroEnergy.Clear();
  Header("AUTO BATTLE","Stage "+battlePlan.StageNumber+"  •  deterministic combat presentation");
  var auto=Tag(content,"AUTO ON",Accent);Set(auto,new Vector2(.05f,.745f),new Vector2(.23f,.79f),Vector2.zero,Vector2.zero);
  var speed=Button(content,"SPEED x"+battleSpeed.ToString("0"),()=>{battleSpeed=battleSpeed<2f?2f:1f;if(speedLabel!=null)speedLabel.text="SPEED x"+battleSpeed.ToString("0");});
  Set(speed.GetComponent<RectTransform>(),new Vector2(.76f,.735f),new Vector2(.95f,.795f),Vector2.zero,Vector2.zero);speed.GetComponent<Image>().color=new Color(.22f,.28f,.40f,1);speedLabel=speed.GetComponentInChildren<Text>();

  var team=Rect("Allies",content,new Vector2(.04f,.49f),new Vector2(.48f,.72f),Vector2.zero,Vector2.zero);Image(team,new Color(.07f,.15f,.18f,.98f));
  string[] slotLabel={"FRONT","FRONT","BACK","BACK","BACK"};
  for(int i=0;i<s.Formation.Slots.Length;i++){
   string id=s.Formation.Slots[i];var d=HeroCatalog.Get(id);float x=(i%2)*.48f+.03f;float y=.69f-(i/2)*.31f;
   if(i>=4){x=.27f;}
   var card=Rect("Hero_"+d.Name,team,new Vector2(x,y-.25f),new Vector2(x+.44f,y),Vector2.zero,Vector2.zero);Image(card,new Color(.12f,.20f,.26f,1));
   var name=Text(card,d.Name+"\n"+slotLabel[i],18,TextAnchor.UpperLeft,Color.white,FontStyle.Bold);Set(name.rectTransform,new Vector2(.05f,.38f),new Vector2(.95f,.94f),Vector2.zero,Vector2.zero);
   Bar(card,new Vector2(.05f,.24f),new Vector2(.95f,.34f),Accent,1f);
   var en=Bar(card,new Vector2(.05f,.08f),new Vector2(.95f,.18f),Energy,.18f);heroEnergy[d.Name]=en;
  }
  var enemy=Rect("Enemy",content,new Vector2(.53f,.49f),new Vector2(.96f,.72f),Vector2.zero,Vector2.zero);Image(enemy,new Color(.22f,.10f,.12f,.98f));
  var enemyTitle=Text(enemy,battlePlan.EnemyName.ToUpper()+"\nSTAGE "+battlePlan.StageNumber,29,TextAnchor.MiddleCenter,Color.white,FontStyle.Bold);Set(enemyTitle.rectTransform,new Vector2(.05f,.36f),new Vector2(.95f,.92f),Vector2.zero,Vector2.zero);
  enemyHpFill=Bar(enemy,new Vector2(.08f,.16f),new Vector2(.92f,.28f),Danger,1f);

  var teamHp=Rect("TeamHPPanel",content,new Vector2(.05f,.42f),new Vector2(.48f,.475f),Vector2.zero,Vector2.zero);Image(teamHp,Panel);
  var th=Text(teamHp,"TEAM HP",17,TextAnchor.MiddleLeft,Muted,FontStyle.Bold);Set(th.rectTransform,new Vector2(.03f,.35f),new Vector2(.30f,.95f),Vector2.zero,Vector2.zero);
  allyHpFill=Bar(teamHp,new Vector2(.31f,.30f),new Vector2(.96f,.70f),Accent,1f);

  battleStatus=Text(content,"Engaging "+battlePlan.EnemyName+"...",31,TextAnchor.MiddleCenter,Color.white,FontStyle.Bold);Set(battleStatus.rectTransform,new Vector2(.06f,.24f),new Vector2(.94f,.40f),Vector2.zero,Vector2.zero);
  var hint=Text(content,"ENERGY builds with normal attacks  •  skills consume energy",20,TextAnchor.MiddleCenter,Muted,FontStyle.Normal);Set(hint.rectTransform,new Vector2(.06f,.17f),new Vector2(.94f,.24f),Vector2.zero,Vector2.zero);
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
    Image e; if(heroEnergy.TryGetValue(beat.ActorName,out e)){float next=beat.Skill?0f:Mathf.Min(1f,energyState[beat.ActorName]+.30f);energyState[beat.ActorName]=next;e.fillAmount=next;}
    battleStatus.text=beat.ActorName+(beat.Skill?" unleashes ULTIMATE":" attacks")+"  •  "+Mathf.RoundToInt(beat.DamagePercent)+"% DAMAGE";
    battleStatus.color=beat.Skill?Orange:Color.white;
   }else{
    allyHp=Mathf.Clamp01(allyHp-beat.DamagePercent/100f);allyHpFill.fillAmount=allyHp;
    battleStatus.text=beat.ActorName+(beat.Skill?" uses OVERDRIVE":" strikes the formation")+"  •  "+Mathf.RoundToInt(beat.DamagePercent)+"% DAMAGE";
    battleStatus.color=Danger;
   }
   DamagePopup(beat.AllyTurn?new Vector2(.74f,.47f):new Vector2(.26f,.47f),"-"+Mathf.RoundToInt(beat.DamagePercent)+"%",beat.AllyTurn?Orange:Danger);
   yield return new WaitForSecondsRealtime(.46f/Mathf.Max(1f,battleSpeed));
  }
  battleStatus.text=battlePlan.Victory?"ENEMY DEFEATED  •  REWARDS SECURED":"FORMATION BROKEN  •  REGROUP";
  battleStatus.color=battlePlan.Victory?Accent:Danger;
  yield return new WaitForSecondsRealtime(.85f/Mathf.Max(1f,battleSpeed));
  battleRoutine=null;Show(View.Result);
 }

 void DamagePopup(Vector2 anchor,string value,Color color){var t=Text(content,value,38,TextAnchor.MiddleCenter,color,FontStyle.Bold);Set(t.rectTransform,anchor-new Vector2(.11f,.025f),anchor+new Vector2(.11f,.035f),Vector2.zero,Vector2.zero);Destroy(t.gameObject,.52f/Mathf.Max(1f,battleSpeed));}

 void BattleResultView(){bool win=result!=null&&result.Victory;Header(win?"VICTORY":"DEFEAT",win?"Rewards secured. Continue pushing.":"Level heroes or adjust formation.");var x=Text(content,win?"VICTORY":"DEFEAT",86,TextAnchor.MiddleCenter,win?Accent:Danger,FontStyle.Bold);Set(x.rectTransform,new Vector2(.05f,.57f),new Vector2(.95f,.82f),Vector2.zero,Vector2.zero);string rew=win?"+"+result.Gold+" Gold   +"+result.HeroXp+" XP   +"+result.Gems+" Gems":"No rewards";var q=Text(content,"Team "+result.TeamPower.ToString("N0")+" vs Enemy "+result.EnemyPower.ToString("N0")+"\n\n"+rew,30,TextAnchor.MiddleCenter,Color.white,FontStyle.Normal);Set(q.rectTransform,new Vector2(.08f,.29f),new Vector2(.92f,.56f),Vector2.zero,Vector2.zero);var b=Button(content,win?"CONTINUE TO STAGE "+s.HighestStage:"RETURN TO HEROES",()=>Show(win?View.Campaign:View.Heroes));Set(b.GetComponent<RectTransform>(),new Vector2(.17f,.10f),new Vector2(.83f,.22f),Vector2.zero,Vector2.zero);b.GetComponent<Image>().color=win?Accent:Orange;}
 void Summon(){Header("SUMMON","Recruit original heroes. Single summon costs 300 Gems.");var star=Text(content,"*",150,TextAnchor.MiddleCenter,Orange,FontStyle.Bold);Set(star.rectTransform,new Vector2(.3f,.59f),new Vector2(.7f,.82f),Vector2.zero,Vector2.zero);var info=Text(content,summonText??"Legendary 3%   •   Epic 22%   •   Rare 75%",28,TextAnchor.MiddleCenter,Color.white,FontStyle.Normal);Set(info.rectTransform,new Vector2(.08f,.37f),new Vector2(.92f,.58f),Vector2.zero,Vector2.zero);var b=Button(content,"SUMMON x1   •   300 GEMS",()=>{var h=s.Summon(new SeededRandom(Environment.TickCount));summonText=h==null?"Not enough Gems.":h.Rarity.ToString().ToUpper()+"\n"+h.Name+"\n"+h.Faction+" / "+h.Role;Show(View.Summon);});Set(b.GetComponent<RectTransform>(),new Vector2(.18f,.19f),new Vector2(.82f,.32f),Vector2.zero,Vector2.zero);b.GetComponent<Image>().color=Orange;var own=Text(content,"Owned "+s.Heroes.Count+" / "+HeroCatalog.All.Length+" heroes",24,TextAnchor.MiddleCenter,Muted,FontStyle.Normal);Set(own.rectTransform,new Vector2(.2f,.08f),new Vector2(.8f,.15f),Vector2.zero,Vector2.zero);}
 int TeamPower(){int p=0;foreach(string id in s.Formation.Slots)p+=BattleSimulator.HeroPower(s.Heroes[id]);return p;}
 void Card(float ymin,float ymax,string a,string b,Color c){var r=Rect(a,content,new Vector2(.05f,ymin),new Vector2(.95f,ymax),Vector2.zero,Vector2.zero);Image(r,Panel);var x=Text(r,a,22,TextAnchor.UpperLeft,Muted,FontStyle.Bold);Set(x.rectTransform,new Vector2(.04f,.54f),new Vector2(.96f,.92f),Vector2.zero,Vector2.zero);var y=Text(r,b,37,TextAnchor.LowerLeft,c,FontStyle.Bold);Set(y.rectTransform,new Vector2(.04f,.08f),new Vector2(.96f,.58f),Vector2.zero,Vector2.zero);}
 static RectTransform Tag(Transform p,string value,Color color){var r=Rect("Tag",p,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);Image(r,new Color(color.r*.35f,color.g*.35f,color.b*.35f,1));var t=Text(r,value,18,TextAnchor.MiddleCenter,color,FontStyle.Bold);Set(t.rectTransform,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero);return r;}
 static Image Bar(Transform p,Vector2 amin,Vector2 amax,Color fillColor,float value){var bg=Rect("Bar",p,amin,amax,Vector2.zero,Vector2.zero);Image(bg,new Color(.04f,.05f,.08f,1));var fr=Rect("Fill",bg,Vector2.zero,Vector2.one,new Vector2(3,3),new Vector2(-3,-3));var fi=fr.gameObject.AddComponent<Image>();fi.color=fillColor;fi.type=UnityEngine.UI.Image.Type.Filled;fi.fillMethod=UnityEngine.UI.Image.FillMethod.Horizontal;fi.fillOrigin=0;fi.fillAmount=Mathf.Clamp01(value);return fi;}
 static GameObject GO(string n,Transform p,params Type[] t){var g=new GameObject(n,t);g.transform.SetParent(p,false);return g;}
 static RectTransform Rect(string n,Transform p,Vector2 amin,Vector2 amax,Vector2 omin,Vector2 omax){var g=GO(n,p,typeof(RectTransform));var r=(RectTransform)g.transform;Set(r,amin,amax,omin,omax);return r;}
 static void Set(RectTransform r,Vector2 amin,Vector2 amax,Vector2 omin,Vector2 omax){r.anchorMin=amin;r.anchorMax=amax;r.offsetMin=omin;r.offsetMax=omax;}
 static void Image(RectTransform r,Color c){var i=r.gameObject.GetComponent<Image>()??r.gameObject.AddComponent<Image>();i.color=c;}
 static Text Text(Transform p,string v,int size,TextAnchor a,Color c,FontStyle s){var g=GO("Text",p,typeof(RectTransform),typeof(Text));var t=g.GetComponent<Text>();t.font=Resources.GetBuiltinResource<Font>("Arial.ttf");t.text=v;t.fontSize=size;t.alignment=a;t.color=c;t.fontStyle=s;t.horizontalOverflow=HorizontalWrapMode.Wrap;t.verticalOverflow=VerticalWrapMode.Truncate;return t;}
 static Button Button(Transform p,string label,Action action){var g=GO("Button",p,typeof(RectTransform),typeof(Image),typeof(Button));g.GetComponent<Image>().color=new Color(.18f,.23f,.34f,1);var b=g.GetComponent<Button>();b.onClick.AddListener(()=>action());var t=Text(g.transform,label,23,TextAnchor.MiddleCenter,Color.white,FontStyle.Bold);Set(t.rectTransform,Vector2.zero,Vector2.one,new Vector2(6,4),new Vector2(-6,-4));return b;}
 static void Clear(Transform t){for(int i=t.childCount-1;i>=0;i--)Destroy(t.GetChild(i).gameObject);}
}
}
