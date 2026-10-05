using System;
using System.Collections.Generic;
using System.Linq;

namespace IdleSlime.Core {
[Serializable]
public sealed class NarrativeBeat {
 public int Stage;
 public string ArcId, ArcTitle, ChapterTitle, StageTitle, Summary, SystemMessage, FeaturedHeroId, VisualKey;
 public NarrativeBeat(int stage,string arcId,string arcTitle,string chapterTitle,string stageTitle,string summary,string systemMessage,string featuredHeroId,string visualKey){
  Stage=stage;ArcId=arcId;ArcTitle=arcTitle;ChapterTitle=chapterTitle;StageTitle=stageTitle;Summary=summary;SystemMessage=systemMessage;FeaturedHeroId=featuredHeroId;VisualKey=visualKey;
 }
}
[Serializable]
public sealed class HeroDestiny {
 public string HeroId, FirstTimelineTitle, FirstTimelineFate, SecondTimelineHook, Secret;
 public HeroDestiny(string heroId,string title,string fate,string hook,string secret){HeroId=heroId;FirstTimelineTitle=title;FirstTimelineFate=fate;SecondTimelineHook=hook;Secret=secret;}
}
public static class AwakenedRealmsNarrative {
 public const string ProtagonistTitle="The Second Awakened";
 public const string AuthorityName="Sovereign of Echoes";
 public const string CollapseName="Realm Collapse";
 public const string Premise="In the first timeline, the protagonist awakened with no recognized class and survived as a disposable porter while the Five Realms fell one by one. At the final breach he witnessed the hidden mechanism behind the Realm Collapse and died with humanity. He awakens twelve years earlier on the morning of his failed Awakening, carrying memories of heroes, disasters, relics, betrayals and deaths that have not happened yet. The Realm marks his soul as an impossible duplicate and grants the forbidden authority Sovereign of Echoes, letting him bind the unrealized destinies of future legends. Every intervention saves lives and corrupts the future he remembers.";
 public static readonly string[] OpeningSystemMessages={
  "[UNRECORDED SOUL DETECTED]",
  "[TEMPORAL DUPLICATION CONFIRMED]",
  "[THE REALM HAS RECOGNIZED YOUR SECOND EXISTENCE]",
  "[UNIQUE AUTHORITY AWAKENED: SOVEREIGN OF ECHOES]",
  "[WARNING: ALTERED DESTINIES WILL ACCELERATE FUTURE DIVERGENCE]"
 };
 static NarrativeBeat B(int s,string a,string at,string c,string st,string sum,string sys,string hero,string visual){return new NarrativeBeat(s,a,at,c,st,sum,sys,hero,visual);}
 public static readonly NarrativeBeat[] Beats={
  B(1,"arc01","The Day Fate Repeated","Chapter 1: I Died Here Once","Ash Before Dawn","He wakes in the same dormitory where his first life began, hours before the Awakening Ceremony. Smoke in the street triggers memories of the final city burning.","[TIMELINE ANCHOR: 12 YEARS BEFORE COLLAPSE]","cinder","cg_regression_wakeup"),
  B(2,"arc01","The Day Fate Repeated","Chapter 1: I Died Here Once","The Broken Crystal","The public crystal again labels him Unclassified. A second message appears for his eyes alone.","[UNRECORDED SOUL DETECTED]","lux","cg_awaken_crystal"),
  B(3,"arc01","The Day Fate Repeated","Chapter 2: A Power That Should Not Exist","Sovereign of Echoes","His hidden authority reveals unfinished destinies instead of fixed classes.","[UNIQUE AUTHORITY AWAKENED: SOVEREIGN OF ECHOES]","solenne","cg_sovereign_authority"),
  B(4,"arc01","The Day Fate Repeated","Chapter 2: A Power That Should Not Exist","The Girl Who Burns Tomorrow","He finds Cinder before she becomes the Phoenix Warden, the first great hero he remembers dying.","[FUTURE LEGEND LOCATED]","cinder","cg_cinder_street"),
  B(5,"arc01","The Day Fate Repeated","Chapter 3: Stealing the First Miracle","The Emberglass Vault","He enters a hidden dungeon three months before history says it was discovered.","[HIDDEN DUNGEON DISCOVERED AHEAD OF HISTORY]","brasa","cg_emberglass_vault"),
  B(6,"arc01","The Day Fate Repeated","Chapter 3: Stealing the First Miracle","A Shield for the Wrong Person","Brasa, a disgraced guard who died nameless in the old future, blocks a fatal blow.","[DESTINY DEVIATION +0.8%]","brasa","cg_brasa_intercept"),
  B(7,"arc01","The Day Fate Repeated","Chapter 4: The First Divergence","History Misses Its Mark","The vault boss appears early, carrying mutations that never existed before.","[WARNING: EVENT NOT PRESENT IN PRIOR TIMELINE]","cinder","cg_mutated_vault_boss"),
  B(8,"arc01","The Day Fate Repeated","Chapter 4: The First Divergence","Echo Contract","Cinder accepts an Echo contract and touches the power of the legend she was meant to become.","[ECHO CONTRACT ESTABLISHED]","cinder","cg_echo_contract_cinder"),
  B(9,"arc01","The Day Fate Repeated","Chapter 5: Someone Changed This","The Wrong Corpse","A dead assassin carries the crest of a guild that should not exist for six more years.","[CAUSAL INCONSISTENCY DETECTED]","nyx","cg_assassin_crest"),
  B(10,"arc01","The Day Fate Repeated","Chapter 5: Someone Changed This","The Message From Tomorrow","A black letter appears in his inventory: You were not the only one sent back.","[FUTURE DIVERGENCE: 4.1%]","nyx","cg_black_letter"),
  B(11,"arc02","Before They Became Legends","Chapter 6: The Archer Beneath the Harbor","The Drowned District","He reaches the Tide capital before the harbor disaster that once forged Mistral into a legend.","[FUTURE LEGEND LOCATED]","mistral","cg_tide_harbor"),
  B(12,"arc02","Before They Became Legends","Chapter 6: The Archer Beneath the Harbor","An Arrow Against the Sea","Saboteurs strike the floodgates months early, proving history is already moving against him.","[HISTORICAL EVENT ADVANCED]","mistral","cg_mistral_floodgate"),
  B(13,"arc02","Before They Became Legends","Chapter 7: The Healer Who Was Supposed to Vanish","Moonlit Clinic","Maris treats refugees in secret. In the first life her disappearance became an unsolved mystery.","[ECHO RESONANCE DETECTED]","maris","cg_maris_clinic"),
  B(14,"arc02","Before They Became Legends","Chapter 7: The Healer Who Was Supposed to Vanish","The Price of Knowing","Saving Maris exposes the party to an intelligence network years before it should know their names.","[HOSTILE OBSERVER ACQUIRED]","maris","cg_hidden_observer"),
  B(15,"arc02","Before They Became Legends","Chapter 8: The Forest That Remembers","Worldroot's Whisper","Briar hears the Worldroot speak the protagonist's first-life name, a name nobody in this timeline knows.","[TEMPORAL MEMORY LEAK DETECTED]","briar","cg_worldroot_whisper"),
  B(16,"arc02","Before They Became Legends","Chapter 8: The Forest That Remembers","The Sleeping Colossus","A dormant guardian wakes because the Realm recognizes the protagonist as a contradiction.","[REALM DEFENSE RESPONSE ACTIVE]","briar","cg_worldroot_colossus"),
  B(17,"arc02","Before They Became Legends","Chapter 9: A Witch With No Future","Bloom Hex","Fern confesses that she dreams of dying in places she has never visited.","[UNOWNED ECHO MEMORY DETECTED]","fern","cg_fern_dream"),
  B(18,"arc02","Before They Became Legends","Chapter 9: A Witch With No Future","The Impossible Memory","Fern describes the exact red sky from the last day of the first timeline.","[CAUSAL INCONSISTENCY ESCALATED]","fern","cg_red_sky_memory"),
  B(19,"arc02","Before They Became Legends","Chapter 10: Five Names on a List","The Kill Order","An assassination ledger names five future heroes who are still unknown to the public.","[FUTURE-KNOWLEDGE SIGNATURE CONFIRMED]","vesper","cg_kill_ledger"),
  B(20,"arc02","Before They Became Legends","Chapter 10: Five Names on a List","A Hunter in the Rain","Vesper intercepts the assassin sent for him and asks how the protagonist knows what he will become.","[FUTURE DIVERGENCE: 11.7%]","vesper","cg_vesper_rain"),
  B(21,"arc03","The Academy of False Prophets","Chapter 11: Entering the Lion's Den","The Ranking Exam","The party enters the elite Awakener academy under false records to reach a sealed relic before the great guilds.","[IDENTITY MASK ACTIVE]","tavi","cg_academy_gate"),
  B(22,"arc03","The Academy of False Prophets","Chapter 11: Entering the Lion's Den","Rank Zero","The protagonist scores last on purpose while directing his companions to impossible victories.","[OBSERVATION PRESSURE INCREASING]","tavi","cg_rank_exam"),
  B(23,"arc03","The Academy of False Prophets","Chapter 12: The Saint Before Her Halo","A Perfect Fraud","Solenne is worshiped as a future saint, yet he remembers her becoming the church's greatest heretic.","[CONTRADICTORY DESTINY DETECTED]","solenne","cg_solenne_chapel"),
  B(24,"arc03","The Academy of False Prophets","Chapter 12: The Saint Before Her Halo","The Light Beneath the Altar","They discover the academy siphoning divine energy from captive Awakened students.","[FORBIDDEN REALM DEVICE LOCATED]","lux","cg_chapel_device"),
  B(25,"arc03","The Academy of False Prophets","Chapter 13: The Saint's First Sin","Burn the Records","Solenne chooses to destroy the institution that manufactured her future reputation.","[DESTINY BRANCH FORMED]","solenne","cg_solenne_burn_records"),
  B(26,"arc03","The Academy of False Prophets","Chapter 13: The Saint's First Sin","The Boy With the Lantern","Lux, a healer who died before graduation in the old future, sees Echo threads without being told they exist.","[AUTHORITY VISIBILITY ANOMALY]","lux","cg_lux_lantern"),
  B(27,"arc03","The Academy of False Prophets","Chapter 14: The First Prophet","A Man Who Knows My Name","The headmaster addresses the protagonist by a title he earned only at the end of his first life.","[SECOND TEMPORAL ACTOR CONFIRMED]","nyx","cg_headmaster_reveal"),
  B(28,"arc03","The Academy of False Prophets","Chapter 14: The First Prophet","The Future Is Property","The headmaster claims regression is ownership of a timeline, and someone paid for both of them to return.","[ORIGIN OF REGRESSION: UNKNOWN PATRON]","nyx","cg_future_property"),
  B(29,"arc03","The Academy of False Prophets","Chapter 15: Collapse Event Zero","The Sky Cracks Early","A miniature Realm Collapse opens above the academy ten years ahead of history.","[REALM COLLAPSE PRECURSOR DETECTED]","solenne","cg_early_rift"),
  B(30,"arc03","The Academy of False Prophets","Chapter 15: Collapse Event Zero","The Hero Who Remembers Dying","Cinder sees her first-timeline death through the Echo bond and chooses to fight anyway.","[ECHO MEMORY TRANSFER: IRREVERSIBLE]","cinder","cg_cinder_memory"),
  B(31,"arc04","Guild War of the Unwritten Future","Chapter 16: History Has Hunters","Wanted by Tomorrow","Major guilds receive bounties for crimes the protagonist has not committed yet.","[PRECRIME RECORD DETECTED]","mistral","cg_future_warrant"),
  B(32,"arc04","Guild War of the Unwritten Future","Chapter 16: History Has Hunters","The Black Comet","Nyx is ordered to kill him and instead demands proof that her younger sister can still be saved.","[LEGENDARY DESTINY NEGOTIATION]","nyx","cg_nyx_rooftop"),
  B(33,"arc04","Guild War of the Unwritten Future","Chapter 17: The Debt of an Assassin","A Death Scheduled Twice","The party intercepts the murder that once broke Nyx, but the killer is replaced by something wearing a human body.","[NONHUMAN TEMPORAL AGENT DETECTED]","nyx","cg_echo_assassin"),
  B(34,"arc04","Guild War of the Unwritten Future","Chapter 17: The Debt of an Assassin","Black Comet Rewritten","Nyx forms an Echo contract on her own terms and surpasses her remembered future power years early.","[DESTINY OUTPUT EXCEEDS PRIOR TIMELINE]","nyx","cg_nyx_contract"),
  B(35,"arc04","Guild War of the Unwritten Future","Chapter 18: The Market of Dead Futures","Auction of Prophecies","An underground market sells relics recovered from futures that never happened.","[PARALLEL TIMELINE MATERIAL CONFIRMED]","pippin","cg_future_auction"),
  B(36,"arc04","Guild War of the Unwritten Future","Chapter 18: The Market of Dead Futures","The Lucky Nobody","Pippin buys a worthless seed the protagonist recognizes as the Worldseed that once ended a continental famine.","[FUTURE RELIC SECURED]","pippin","cg_worldseed"),
  B(37,"arc04","Guild War of the Unwritten Future","Chapter 19: War for a Tomorrow","Five Banners","The great guilds mobilize around rival prophecies. Every faction believes controlling him means controlling the future.","[CONTINENTAL CONFLICT THRESHOLD REACHED]","brasa","cg_five_banners"),
  B(38,"arc04","Guild War of the Unwritten Future","Chapter 19: War for a Tomorrow","The Guardian Who Refuses a Crown","Brasa rejects his old order and declares the party an independent Realm company: Echobound.","[NEW FACTION REGISTERED: ECHOBOUND]","brasa","cg_brasa_banner"),
  B(39,"arc04","Guild War of the Unwritten Future","Chapter 20: The Other Regressor","A Familiar Sword","The second regressor appears carrying a weapon the protagonist personally buried in the first timeline.","[TEMPORAL IDENTITY MATCH FAILED]","vesper","cg_second_regressor"),
  B(40,"arc04","Guild War of the Unwritten Future","Chapter 20: The Other Regressor","You Were Supposed to Stay Dead","The stranger claims the protagonist stole a regression that was meant for someone else.","[FUTURE DIVERGENCE: 37.4%]","vesper","cg_regressor_duel"),
  B(41,"arc05","The First Realm Falls","Chapter 21: Ten Years Too Soon","The Ember Capital Burns","The first major Collapse begins a decade early. The city matches his death memory, but the people inside do not.","[REALM COLLAPSE PHASE I INITIATED]","cinder","cg_ember_capital_burns"),
  B(42,"arc05","The First Realm Falls","Chapter 21: Ten Years Too Soon","Phoenix Warden","Cinder reaches the power she once gained after ten years of war, this time without dying for it.","[LEGENDARY DESTINY COMPLETED EARLY]","cinder","cg_phoenix_warden"),
  B(43,"arc05","The First Realm Falls","Chapter 22: The Enemy Behind the System","The Voice Between Messages","A human voice speaks through the Realm interface and asks why the protagonist is still alive.","[SYSTEM INTEGRITY COMPROMISED]","fern","cg_system_voice"),
  B(44,"arc05","The First Realm Falls","Chapter 22: The Enemy Behind the System","Sovereign's Tax","Full-scale Echo power begins erasing pieces of his first-life memories.","[AUTHORITY COST DISCOVERED: MEMORY CONSUMPTION]","maris","cg_memory_shatter"),
  B(45,"arc05","The First Realm Falls","Chapter 23: What I Refuse to Forget","Names Before Victory","Maris makes him record the names and promises he is starting to lose, turning the party into guardians of his history.","[MEMORY ANCHOR CREATED]","maris","cg_memory_journal"),
  B(46,"arc05","The First Realm Falls","Chapter 23: What I Refuse to Forget","The Null Queen","A young girl appears at the center of the Collapse. He recognizes the future Null Queen years before her corruption.","[CATASTROPHE ENTITY LOCATED: PRE-AWAKENED]","lux","cg_null_queen_child"),
  B(47,"arc05","The First Realm Falls","Chapter 24: Kill the Demon Lord Before She Exists","The Choice Everyone Knows","The second regressor demands the girl's execution. Every remembered future supports him.","[OPTIMAL SURVIVAL PATH: TERMINATE TARGET]","solenne","cg_execution_choice"),
  B(48,"arc05","The First Realm Falls","Chapter 24: Kill the Demon Lord Before She Exists","The Choice I Already Regret","The protagonist refuses to murder a child for crimes from a discarded future.","[PRIOR TIMELINE AUTHORITY REJECTED]","pippin","cg_save_null_child"),
  B(49,"arc05","The First Realm Falls","Chapter 25: A Future With No Map","Beyond My Memories","The battle ends in an outcome that never existed. His future knowledge becomes unreliable overnight.","[FUTURE DIVERGENCE: 51.2%]","tavi","cg_unwritten_future"),
  B(50,"arc05","The First Realm Falls","Chapter 25: A Future With No Map","Season One: The Third Timeline","The rescued girl wakes and calls him by a name he never used in either life. A third set of memories flashes across the sky.","[UNKNOWN TIMELINE DETECTED]","cinder","cg_third_timeline")
 };
 public static readonly HeroDestiny[] Destinies={
  new HeroDestiny("cinder","Phoenix Warden","Died holding the capital gate during the first Realm Collapse.","Recruit her before the Emberglass Vault and let her become a legend without requiring martyrdom.","Her Echo remembers the moment she died."),
  new HeroDestiny("brasa","Ashen Bastion","Died nameless in a dungeon before his defensive talent was recognized.","Save the disgraced guard and make his loyalty the foundation of the Echobound.","He was meant to command the order that later hunted you."),
  new HeroDestiny("mistral","Horizon Spear","Became the Tide Realm's greatest ranger after losing her home.","Prevent the disaster that forged her without weakening the legend she becomes.","She holds a map to a breach that has not opened yet."),
  new HeroDestiny("maris","Moon-Tide Saint","Vanished while investigating illegal healing experiments.","Find her hidden clinic before the intelligence network erases her.","Her healing stabilizes memories consumed by Sovereign of Echoes."),
  new HeroDestiny("briar","Worldroot Guardian","Awakened only after the Verdant Realm was nearly destroyed.","Wake the guardian without sacrificing the forest around him.","The Worldroot remembers multiple timelines."),
  new HeroDestiny("fern","Thorn Witch","Executed as a heretic after predicting disasters nobody believed.","Treat her impossible dreams as evidence instead of madness.","She dreams timelines the protagonist never lived."),
  new HeroDestiny("solenne","Sun-Crowned Heretic","Began as a saint and ended as the church's greatest enemy.","Expose the institution shaping her destiny before faith becomes a prison.","Her future heresy was the first correct theory of the Realm system."),
  new HeroDestiny("lux","Last Beacon","Died before graduation and became a footnote in another hero's biography.","Keep the quiet healer alive long enough to reveal his abnormal sight.","He sees Echo threads without possessing the authority."),
  new HeroDestiny("nyx","Black Comet","Became an assassin queen after her sister's murder.","Stop the murder without stealing her agency or turning her into a weapon.","She was contracted to kill the protagonist in the first timeline."),
  new HeroDestiny("vesper","Eclipse Blade","Survived every guild war and vanished after the final breach.","Recruit the hunter who notices contradictions faster than anyone.","He knows the second regressor's fighting style."),
  new HeroDestiny("pippin","Fortune Gardener","Never became famous but accidentally saved millions.","Protect the lucky nobody whose harmless choices repeatedly alter history.","His luck spikes near timeline fractures."),
  new HeroDestiny("tavi","Redline Prodigy","Died young chasing academy rank records.","Redirect the speed-obsessed prodigy toward battles worth winning.","He becomes the first person to outrun a collapsing Realm boundary.")
 };
 static readonly Dictionary<int,NarrativeBeat> ByStage=Beats.ToDictionary(x=>x.Stage);
 static readonly Dictionary<string,HeroDestiny> ByHero=Destinies.ToDictionary(x=>x.HeroId);
 public static NarrativeBeat ForStage(int stage){NarrativeBeat beat;return ByStage.TryGetValue(stage,out beat)?beat:null;}
 public static HeroDestiny ForHero(string heroId){HeroDestiny destiny;return heroId!=null&&ByHero.TryGetValue(heroId,out destiny)?destiny:null;}
 public static IEnumerable<NarrativeBeat> ForArc(string arcId){return Beats.Where(x=>x.ArcId==arcId).OrderBy(x=>x.Stage);}
}
}
