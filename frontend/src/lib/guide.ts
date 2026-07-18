import type { DeckVariant, FeaturedCards } from './types';

// ── Output types ───────────────────────────────────────────────────────────────

export type FitBadge = 'Recommended' | 'Viable' | 'Experimental';

export interface MulliganAdvice {
  keepHandsWith: string[];
  mulliganIf: string;
  scoreSummary: string;
}

export interface PlayGuide {
  commanderName: string;
  strategyName: string;
  fitBadge: FitBadge;
  macroPlan: string;
  howItWins: string;
  earlyGame: string;
  midGame: string;
  lateGame: string;
  mulligan: MulliganAdvice;
  keyEngines: string[];
  keyFinishers: string[];
  keyInteraction: string[];
  keyProtection: string[];
  keySetup: string[];
  keyRamp: string[];
  interactionAdvice: string;
  commonMistakes: string[];
  warnings: string[];
}

// ── Strategy template definitions ─────────────────────────────────────────────

interface RoleWarning {
  role: string;
  min: number;
  message: string;
}

interface StrategyTemplate {
  ids: string[];        // strategy IDs this template covers
  macroPlan: string;
  howItWins: string;
  earlyGame: string;
  midGame: string;
  lateGame: string;
  keepHandsWith: string[];
  mulliganIf: string;
  interactionAdvice: string;
  commonMistakes: string[];
  roleWarnings: RoleWarning[];
}

const STRATEGY_TEMPLATES: StrategyTemplate[] = [
  {
    ids: ['spellslinger_tempo'],
    macroPlan: 'Stay ahead on cards, answer the scariest threats, and close with a well-protected finisher.',
    howItWins: 'You win by trading spells efficiently, keeping your hand stocked, and resolving a game-ending threat once opponents are constrained. Every spell is a resource — never tap out without a plan.',
    earlyGame: 'Hold up mana for interaction on opponents\' turns. On your turn, cast cheap cantrips and card selection spells to build hand quality. You can absorb early damage — you\'re building toward the mid-game.',
    midGame: 'Counter the spells that matter; let the small stuff resolve. Start applying pressure with an engine or early finisher while keeping interaction open. Your card advantage should be pulling ahead.',
    lateGame: 'Resolve your finisher with mana open for protection. One or two threats are enough — you want opponents to run out of answers before you run out of cards.',
    keepHandsWith: [
      'At least 3 lands, including blue mana',
      'At least one cheap spell to cast before turn 3',
      'At least one piece of interaction (counter or removal)',
      'Something to filter or dig toward your threats',
    ],
    mulliganIf: 'You have only expensive spells (nothing before turn 4), or no interaction at all. A 6-card hand with a counter and a cantrip beats a 7-card hand that can\'t do anything early.',
    interactionAdvice: 'Save counterspells for game-winning spells and dangerous combo pieces. Use removal for the most threatening creatures — not the first one that comes down.',
    commonMistakes: [
      'Tapping out to cast a threat with no mana up to protect it',
      'Countering early ramp spells — save counters for win conditions',
      'Not using card selection aggressively; dig for answers every chance you get',
    ],
    roleWarnings: [
      { role: 'counterspell', min: 5, message: 'Light counter suite — be selective about what you counter. Prioritize opponent win conditions over value plays.' },
      { role: 'draw', min: 6, message: 'Low card draw — you may run dry in longer games. Prioritize drawing cards over most other plays.' },
    ],
  },

  {
    ids: ['tokens_go_wide', 'typal_midrange'],
    macroPlan: 'Flood the board with creatures, build critical mass, and attack for lethal with pump or sheer numbers.',
    howItWins: 'You win by going wider than opponents can answer. When you have enough bodies, a single pump effect or attack step ends the game. Speed and pressure are your advantages.',
    earlyGame: 'Play a creature or token maker every turn. Do not hold back cheap token makers waiting for the "right time" — every creature you delay is a turn of damage lost.',
    midGame: 'Build to critical mass. Look for anthem effects or payoffs that turn your tokens into a real threat. Start attacking when you can chip in damage safely.',
    lateGame: 'Go all-in. If you have the board advantage, attack with everything. This archetype is vulnerable to sweepers — do not give opponents time to stabilize with a board-wipe.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one creature or token maker you can cast before turn 3',
      'A payoff or anthem if possible — or a way to find one',
    ],
    mulliganIf: 'You have only reactive cards (counters, removal) with no pressure. You need to start making threats early or you fall behind immediately.',
    interactionAdvice: 'Use removal to clear blockers when you\'re about to attack for lethal. Save wide-board sweepers for when opponents threaten to stabilize.',
    commonMistakes: [
      'Holding back creatures instead of attacking — you win through damage, not waiting',
      'Not committing pump effects at the right moment; time them with an attack, not before',
      'Overextending into an obvious sweeper when you could attack first',
    ],
    roleWarnings: [
      { role: 'engine', min: 4, message: 'Light token production engines — if the board gets wiped, rebuilding will be slow. Treat the token theme as incidental pressure rather than the main plan.' },
      { role: 'ramp', min: 4, message: 'Low ramp — you may not be able to cast anthems or payoffs on curve. Prioritize ramp picks when building.' },
    ],
  },

  {
    ids: ['graveyard_reanimator'],
    macroPlan: 'Fill the graveyard with big threats and bring them back for much less than their normal cost.',
    howItWins: 'You win by replaying the best threats in the game repeatedly. A single reanimation target can change the board state instantly, and opponents can\'t answer the same thing forever.',
    earlyGame: 'Fill the graveyard. Cast filtering spells, self-mill effects, and discard outlets. Don\'t cast your big threats from hand unless you absolutely must — they\'re better reanimated.',
    midGame: 'Start returning threats. A well-timed reanimation spell can win the game from behind. Keep your graveyard stocked so you always have options.',
    lateGame: 'You should have enough recursion to be playing multiple threats per turn. Stay ahead by returning the most impactful card, not just any card.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'A way to get something into the graveyard early (filter, mill, or discard outlet)',
      'At least one reanimation spell, or a tutor to find one',
    ],
    mulliganIf: 'You have big threats but no way to get them into the graveyard, or you have graveyard fillers but no reanimation. You need both halves.',
    interactionAdvice: 'Graveyard decks are often light on interaction. Use removal on the most threatening permanents and save counters for graveyard hate — that\'s what shuts you down.',
    commonMistakes: [
      'Casting your big reanimation targets from hand instead of putting them in the graveyard',
      'Not protecting key recursion engines from removal',
      'Not playing around graveyard hate — have a plan when they exile your graveyard',
    ],
    roleWarnings: [
      { role: 'engine', min: 3, message: 'Light graveyard recursion engines — the reanimator plan may not fire consistently. Look for upgrade opportunities.' },
      { role: 'draw', min: 5, message: 'Low card draw — you may not find your reanimation targets reliably. Prioritize cantrips and draw spells.' },
    ],
  },

  {
    ids: ['landfall_ramp'],
    macroPlan: 'Play a land every turn, trigger landfall payoffs, and close with a large threat or endless value.',
    howItWins: 'You win by pulling far ahead on mana and triggering landfall effects repeatedly. Once your engine is running, every land drop creates value or damage that opponents cannot keep up with.',
    earlyGame: 'Play every land you can, as early as you can. Prioritize ramp spells that put extra lands directly into play — not ones that just add mana. Every extra land drop is two triggers later.',
    midGame: 'Activate landfall payoffs on repeat. Keep your lands-per-turn count as high as possible. A single fetchland can trigger two landfall effects if you need it.',
    lateGame: 'You should have a large mana lead and recurring landfall triggers. Finish with a big threat or overwhelm with tokens or damage from payoffs.',
    keepHandsWith: [
      'At least 3 lands, ideally with color fixing',
      'At least one ramp spell that puts a land into play (not just mana)',
      'A landfall payoff, or a tutor to find one',
    ],
    mulliganIf: 'You have no ramp or only one land. You need to hit your land drops every turn — a stumble on mana is unrecoverable.',
    interactionAdvice: 'Use interaction to clear creatures that threaten to race you before you stabilize. After that, focus on your own engine — you will outvalue anyone who doesn\'t interact early.',
    commonMistakes: [
      'Not playing all your lands — even basic lands trigger landfall',
      'Fetching the wrong basics and missing color fixing',
      'Not converting your mana lead to damage fast enough before opponents stabilize',
    ],
    roleWarnings: [
      { role: 'ramp', min: 10, message: 'Low land-into-play ramp — the landfall plan needs consistent extra land drops. This build may struggle to outpace a typical curve.' },
      { role: 'engine', min: 3, message: 'Low landfall payoffs — you may be ramping without enough ways to convert it to value. Look for payoff upgrades.' },
    ],
  },

  {
    ids: ['counters_go_tall'],
    macroPlan: 'Grow one or two creatures to overwhelming size, then attack for lethal with evasion or protection.',
    howItWins: 'You win through commander damage (21) or combat damage from a heavily buffed creature. Your target creature becomes too large to block profitably, and opponents are forced to use removal.',
    earlyGame: 'Get a threat on board as early as possible. A single well-chosen target can win the game if left unchecked. Prioritize creatures that have built-in counter synergy.',
    midGame: 'Stack counters efficiently. Look for proliferate effects, spells that add multiple counters, or copy effects. Protect your key creature above everything else.',
    lateGame: 'Attack with your biggest creature and push through with evasion or protection spells. A 10-power creature with trample or flying usually ends the game in two swings.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'A creature to put counters on, or a way to find one',
      'At least one counter enabler or a protection spell',
    ],
    mulliganIf: 'You have no creature target and no way to find one, or you have creatures but no counters enablers. Without a target, the strategy doesn\'t function.',
    interactionAdvice: 'Your main vulnerability is spot removal. Keep protection spells back for when your key creature is targeted — don\'t use them proactively.',
    commonMistakes: [
      'Spreading counters across multiple creatures instead of dominating with one',
      'Not protecting your key creature — losing it to removal sets you back several turns',
      'Running out of mana to protect at exactly the wrong moment',
    ],
    roleWarnings: [
      { role: 'protection', min: 4, message: 'Low protection — your key creature is vulnerable to spot removal. Prioritize hexproof and indestructible effects.' },
      { role: 'engine', min: 3, message: 'Light counter synergy engines — the counters plan may not stack fast enough. You may want to build more conservatively.' },
    ],
  },

  {
    ids: ['artifact_synergy_midrange'],
    macroPlan: 'Chain artifact value triggers, build out your artifact count, and close with a payoff finisher.',
    howItWins: 'You win through incremental artifact value that compounds over multiple turns, then convert that advantage into a game-ending payoff creature or combo piece.',
    earlyGame: 'Get low-cost artifacts into play as quickly as possible. Each one generates value over time and turns on your payoff cards. Prioritize mana rocks that also provide synergy.',
    midGame: 'Build out your artifact count. Your payoff effects get exponentially better the more artifacts you have on board. Look for ways to replay or recur key artifacts.',
    lateGame: 'Activate your largest payoffs or attack with a well-equipped artifact creature. By now your card advantage should be insurmountable.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one low-cost artifact or artifact tutor',
      'A payoff card or something to draw into one',
    ],
    mulliganIf: 'You have artifacts but no payoffs and no draw, or payoffs but nothing to trigger them early. The engine needs both pieces.',
    interactionAdvice: 'Use removal on cards that threaten to exile your artifacts or shut down your engine. Artifacts are vulnerable to hate cards — identify and answer those first.',
    commonMistakes: [
      'Not playing artifacts efficiently — every untapped mana could be an artifact',
      'Not protecting key artifact payoff creatures from removal',
      'Ignoring recursion spells — a returned artifact is almost always better than a new one',
    ],
    roleWarnings: [
      { role: 'draw', min: 6, message: 'Low card draw — you may run out of gas between artifact plays. Prioritize draw effects early.' },
      { role: 'ramp', min: 5, message: 'Low ramp — artifact decks need mana to deploy multiple cards per turn. This build may be slower than expected.' },
    ],
  },

  {
    ids: ['enchantress_control'],
    macroPlan: 'Generate card advantage through enchantments, lock down the board, and close with a big threat.',
    howItWins: 'You win by out-carding everyone. Each enchantment draws you cards, which finds more enchantments, which draws more cards. Once your engine is running, you have more answers than anyone has questions.',
    earlyGame: 'Play cheap enchantments immediately. If your commander draws cards on enchantments, even a 1-mana enchantment is card neutral at worst. The earlier you start, the more value you get.',
    midGame: 'Snowball the advantage. Your draw engine should be producing multiple cards per turn cycle. Use the extra cards to find answers for everything threatening.',
    lateGame: 'Close with a large enchantment-based finisher or through pure card advantage — your opponent will be out of resources long before you are.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one enchantment you can cast before turn 3',
      'A draw payoff or your enchantress commander ready to come down',
    ],
    mulliganIf: 'You have no enchantments early and no draw — without the engine starting, you are just a slow value deck with no payoff.',
    interactionAdvice: 'Use enchantment-based removal (Banishment, Arrested Development) to answer threats permanently. Save counterspells for enchantment hate cards.',
    commonMistakes: [
      'Not playing around enchantment-specific removal — not all removal exiles, but enchantment hate often does',
      'Spending too many cards on reactive enchantments instead of building the value engine',
      'Not closing the game once you have an overwhelming card advantage lead',
    ],
    roleWarnings: [
      { role: 'engine', min: 4, message: 'Light enchantment engines — the snowball may not start fast enough. This build plays more like a control deck than a pure enchantress.' },
      { role: 'protection', min: 3, message: 'Low protection for your key pieces — enchantresses are high-value targets for removal.' },
    ],
  },

  {
    ids: ['lifegain_midrange'],
    macroPlan: 'Gain life on a trigger chain, convert those triggers into card advantage or a drain kill.',
    howItWins: 'You win by turning life gain into power — either through drain effects that lower opponents\' life totals while you raise yours, or by using life gain payoffs that generate enough advantage to overwhelm.',
    earlyGame: 'Start gaining life as early as possible. Even small amounts of life gain trigger your payoffs. Prioritize creatures and spells that gain life on cast or trigger, not just combat.',
    midGame: 'Stack your payoffs. A single soul sisters effect combined with multiple lifegain sources can generate huge value. Look for drain payoffs that close the gap on opponents.',
    lateGame: 'Drain opponents out or overwhelm with creature tokens buffed by lifegain payoffs. At this point you should have a large life total advantage to work with.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one early lifegain source (turn 1-2 if possible)',
      'A payoff that cares about lifegain, or something to find one',
    ],
    mulliganIf: 'You have payoffs but nothing to trigger them, or you have lifegain sources but no payoffs. Both halves need to be present.',
    interactionAdvice: 'Protect your key lifegain payoff creatures above everything else. They are the engine — losing them means you are just gaining life with no benefit.',
    commonMistakes: [
      'Gaining life with no payoff in play — it does nothing without the engine',
      'Not attacking when you can win through drain; life totals are a resource to convert to damage',
      'Not protecting key payoff creatures from spot removal',
    ],
    roleWarnings: [
      { role: 'engine', min: 4, message: 'Light lifegain payoff engines — you may be gaining life without converting it to advantage. Treat lifegain as incidental unless you find more payoffs.' },
      { role: 'finisher', min: 2, message: 'Low finishers — you may build a large life total with no way to convert it to lethal. Look for drain or combat finishers.' },
    ],
  },

  {
    ids: ['aura_voltron'],
    macroPlan: 'Load the commander with auras, gain evasion and protection, and swing for 21 commander damage.',
    howItWins: 'You win through 21 commander damage. One well-equipped commander with flying or unblockability can close the game in 3-4 swings, especially with double strike.',
    earlyGame: 'Cast your commander as early as possible. Do not wait for the "right moment" — the longer it is in the command zone, the more commander tax you pay later. Get it in play and start suiting up.',
    midGame: 'Prioritize auras that grant evasion (flying, unblockable, shadow) and protection (hexproof, ward). These two properties make your commander nearly impossible to stop.',
    lateGame: 'Attack every turn once your commander is suited up. With double strike and enough power, you can close in two swings. Keep a protection spell up.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one aura, especially an evasion aura',
      'Protection for your commander, or mana to replay it once',
    ],
    mulliganIf: 'You have auras but no way to land or protect your commander, or you have no auras at all. Without the commander in play, this strategy does nothing.',
    interactionAdvice: 'Use your limited interaction on removal spells that target your commander and effects that wipe the board. Nothing else matters as much.',
    commonMistakes: [
      'Not protecting the commander with hexproof or ward before committing expensive auras',
      'Overloading auras onto an unprotected commander — losing it to removal sets you back by 10+ mana',
      'Not having an evasion aura — a ground-based commander gets chump-blocked indefinitely',
    ],
    roleWarnings: [
      { role: 'protection', min: 5, message: 'Low protection — your commander is highly vulnerable to removal. Losing it with 3+ auras is often game-losing. Prioritize hexproof and ward.' },
      { role: 'ramp', min: 6, message: 'Low ramp — voltron strategies need to replay the commander through tax. Without ramp, a single removal spell can set you back multiple turns.' },
    ],
  },

  {
    ids: ['equipment_voltron'],
    macroPlan: 'Equip the commander with powerful equipment, gain evasion and protection, and swing for 21 commander damage.',
    howItWins: 'You win through 21 commander damage. Unlike aura voltron, equipment sticks around if your commander dies — you pay equip costs again but don\'t lose the equipment.',
    earlyGame: 'Cast cheap equipment early, even if you can\'t equip immediately. Having them on board means you can equip the moment you\'re ready. Cast your commander once equipment is available.',
    midGame: 'Prioritize equipping evasion (flying, trample, unblockable) and protection (hexproof, ward, indestructible). Get your commander to an untouchable state before swinging.',
    lateGame: 'Attack every turn with a protected, evasive commander. Equipment that gives double strike or +4/+4 can close from nowhere.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one equipment you can cast or a tutor for one',
      'Ramp to pay equip costs — they add up fast',
    ],
    mulliganIf: 'You have no equipment and no way to find any, or no way to play your commander by turn 3. Equipment voltron is slow to start if the pieces aren\'t there.',
    interactionAdvice: 'Protect your commander from targeted removal above all. Use your interaction on board-wipes and effects that destroy artifacts.',
    commonMistakes: [
      'Not protecting the commander before swinging — indestructible is often better than more power',
      'Paying equip costs too early when the commander doesn\'t have evasion yet',
      'Ignoring artifact recursion — retrieving key equipment after a board-wipe is often correct',
    ],
    roleWarnings: [
      { role: 'protection', min: 5, message: 'Low protection — your commander can be removed at will. Prioritize hexproof and indestructible equipment.' },
      { role: 'ramp', min: 7, message: 'Low ramp — equip costs add up quickly. Without ramp, you may be stuck replaying the commander instead of equipping it.' },
    ],
  },

  {
    ids: ['big_mana_tap_control'],
    macroPlan: 'Ramp into a mana lead, tap down threats, clear the board, and close with a large finisher.',
    howItWins: 'You win by pulling so far ahead on mana that opponents can\'t interact with your plays. Tap down their best threats, answer the rest, and close with an untouchable finisher.',
    earlyGame: 'Ramp every turn. Every turn without a ramp play is wasted. You need to outpace opponents on mana — that\'s your entire plan for the first 4 turns.',
    midGame: 'Use tap effects to neutralize the most dangerous threats. You don\'t need to kill them, just keep them from attacking or activating. Answer anything that slips through.',
    lateGame: 'You should have a significant mana advantage. Tap down all defenses, cast your finisher with protection open, and attack with it.',
    keepHandsWith: [
      'At least 3 lands, with multiple ramp spells',
      'At least one early ramp spell (turn 2-3)',
      'A removal spell or board-wipe for emergencies',
    ],
    mulliganIf: 'You have only one ramp spell or no ramp at all. Without early ramp, you are just a slow control deck with no payoff.',
    interactionAdvice: 'Use board-wipes to reset when you fall behind. Use tap effects offensively in the late game once you have a mana lead, and defensively in the early game to survive.',
    commonMistakes: [
      'Using tap effects offensively in the early game when you should be using them to survive',
      'Not ramping when you have the opportunity — every land ahead translates to one more spell per turn',
      'Wasting removal too early on creatures that aren\'t a real threat',
    ],
    roleWarnings: [
      { role: 'ramp', min: 10, message: 'Low ramp — big mana decks need consistent land drops and mana acceleration. Without it, the tap control plan may not activate in time.' },
      { role: 'sweeper', min: 2, message: 'Low board-wipes — you may struggle to recover from an early wide attack. Look for at least 2-3 board-wipes.' },
    ],
  },

  {
    ids: ['aristocrats_sacrifice_midrange'],
    macroPlan: 'Loop cheap creatures through sacrifice outlets, triggering death payoffs for damage, cards, or life drain.',
    howItWins: 'You win through repeated death triggers converting into damage or life drain. With the right engine running, each sacrifice can drain 1-3 life from every opponent while drawing you cards and rebuilding the board.',
    earlyGame: 'Get a sacrifice outlet and a cheap creature in play as early as possible. Even one trigger per turn snowballs quickly.',
    midGame: 'Build the full loop. Sacrifice outlet + death trigger payoff + token makers = the engine. Find all three pieces and the game becomes very hard for opponents to win.',
    lateGame: 'Drain opponents out with repeated triggers, or overwhelm with a large board of tokens that your payoffs have made too big to block profitably.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'A sacrifice outlet or a way to find one quickly',
      'At least one death trigger payoff',
    ],
    mulliganIf: 'You have payoffs but no sacrifice outlet, or you have an outlet but nothing to sacrifice and no token makers. The engine needs all three parts.',
    interactionAdvice: 'Use your sacrifice outlet to protect key creatures from targeted removal by sacrificing them in response. This also triggers your death payoffs.',
    commonMistakes: [
      'Not having a sacrifice outlet when all your payoffs require one',
      'Sacrificing key creatures at the wrong time — wait for triggers to stack',
      'Not keeping protection up for the sacrifice outlet itself — losing it ends the engine',
    ],
    roleWarnings: [
      { role: 'engine', min: 4, message: 'Light sacrifice engine — you may be able to sacrifice but not generate enough death triggers. Look for more payoff cards.' },
      { role: 'draw', min: 5, message: 'Low card draw — you may run out of fuel. Prioritize draw-on-death effects to stay in the game.' },
    ],
  },

  // ── Legacy commander profiles ──────────────────────────────────────────────

  {
    ids: ['satoru_toolbox', 'yuffie_ninjutsu'],
    macroPlan: 'Deploy small evasive creatures, use ninjutsu to put huge threats into play for free, and close with overwhelming ETB effects.',
    howItWins: 'You win by cheating large creatures into play via ninjutsu. A single successful ninjutsu attack can put a game-winning creature into play for just 2 mana. Opponents can\'t keep enough blockers to stop every evasive attacker.',
    earlyGame: 'Get an evasive one-drop or two-drop into play on turn 1-2. Small fliers and shadow creatures that can attack freely are your delivery system. If they land a hit, you deploy a massive threat at instant speed.',
    midGame: 'Chain ninjutsu attacks. When one big threat is answered, bounce a ninja back to hand and keep attacking with the base creature. Your massive ETB threats going off multiple times per game is the strategy.',
    lateGame: 'By now you should have resolved multiple large threats. Keep the pressure on — your opponents are playing defense while you keep putting 6+ mana creatures into play for 2.',
    keepHandsWith: [
      'At least 3 lands with blue and black mana',
      'An evasive creature you can cast on turn 1 or 2',
      'At least one large ETB threat or ninjutsu payoff',
      'Interaction to protect your attack step',
    ],
    mulliganIf: 'You have no evasive enablers. A hand of only large threats and interaction can\'t execute the ninjutsu plan — you need small unblockable attackers.',
    interactionAdvice: 'Protect your attack step above all else. Counter spells that would tap down or destroy your evasive creatures. Use removal on the most dangerous blockers.',
    commonMistakes: [
      'Attacking with your big ninjutsu targets instead of keeping them for ninjutsu',
      'Casting your large threats from hand when you should be using them as ninjutsu targets',
      'Not having enough evasive enablers — without them the plan doesn\'t fire',
    ],
    roleWarnings: [
      { role: 'evasive_enabler', min: 10, message: 'Low evasive enabler count — the ninjutsu plan needs consistent evasive attackers. This build may struggle to find the right creatures.' },
      { role: 'etb_payoff', min: 3, message: 'Low ETB payoff count — make sure your ninjutsu targets generate immediate value when they enter.' },
    ],
  },

  {
    ids: ['yuriko_tempo'],
    macroPlan: 'Flood in with one-drops, connect with Yuriko via ninjutsu, and drain opponents with high-CMC reveals every turn.',
    howItWins: 'You win by triggering Yuriko\'s reveal effect every turn, draining opponents for 5-10 life per attack step. With topdeck manipulation, you control what you reveal and deal reliable damage to all opponents simultaneously.',
    earlyGame: 'Turn 1: evasive one-drop. Turn 2: attack with it, ninjutsu Yuriko into play. From there, every attack step triggers at least one Yuriko reveal. The game plan is on rails if you hit this curve.',
    midGame: 'Keep Yuriko alive and attacking. Use topdeck manipulation to put high-CMC cards on top of your library before each attack. A single attack with Yuriko can drain 20+ life across all opponents.',
    lateGame: 'You should be winning or very close. If Yuriko has died multiple times, recasting from the command zone becomes expensive — shift to alternative plans using your large ETB threats.',
    keepHandsWith: [
      'Blue mana and at least one evasive one-drop',
      'A way to recover Yuriko if she\'s removed (ninjutsu lets you replay her for 2U)',
      'Topdeck manipulation to control what you reveal',
    ],
    mulliganIf: 'You have no evasive one-drops. Waiting until turn 3 to deploy a Yuriko vehicle means she comes down on turn 4 at the earliest — far too slow.',
    interactionAdvice: 'Counter anything that would exile Yuriko, stop your attack step, or wipe your evasive one-drops. Other spells are secondary.',
    commonMistakes: [
      'Not using topdeck manipulation before each Yuriko attack — you want the highest-CMC cards on top',
      'Letting Yuriko die to removal without protection ready',
      'Not counting commander damage — Yuriko deals combat damage and can close with that after heavy draining',
    ],
    roleWarnings: [
      { role: 'evasive_enabler', min: 12, message: 'Low evasive enabler count — Yuriko needs consistent attack vehicles. Without enough one-drops, the plan breaks down quickly.' },
      { role: 'topdeck_setup', min: 4, message: 'Low topdeck manipulation — you\'re revealing blind with Yuriko. Add more scry, surveil, or top-of-library effects to maximize drain.' },
    ],
  },

  {
    ids: ['talion_control', 'control'],
    macroPlan: 'Answer every threat, build card advantage, and close once opponents are out of resources.',
    howItWins: 'You win by never losing. Answer every meaningful play opponents make until they have no resources left, then deploy your finisher in a protected position.',
    earlyGame: 'Develop mana and hold up interaction. Counter or remove anything that threatens to get out of hand. Don\'t over-invest early — you want to be reactive.',
    midGame: 'Build card advantage while continuing to answer threats. At this point your card draw should be pulling you ahead. Identify and answer the most dangerous cards opponents can draw.',
    lateGame: 'Deploy your finisher with counterspell backup. You should have more cards than anyone. End the game quickly once you commit — don\'t let opponents find their answers.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one counter or removal spell you can cast before turn 3',
      'Card draw to refill after spending interaction',
    ],
    mulliganIf: 'You have no interaction before turn 4, or only one card draw spell and no way to find more. Control needs both pieces from the start.',
    interactionAdvice: 'Counter the most threatening spells opponents cast — not every spell, just the ones that matter. Let resolved spells you can handle stay on board; counter the ones you can\'t.',
    commonMistakes: [
      'Countering too many early plays and running out of interaction for the spells that matter',
      'Not using card draw aggressively enough — draw cards every turn you can',
      'Waiting too long to deploy your finisher — once you have the advantage, close the game',
    ],
    roleWarnings: [
      { role: 'counterspell', min: 6, message: 'Low counterspell count — you may not have enough interaction to answer everything. Be very selective about what you counter.' },
      { role: 'sweeper', min: 2, message: 'Low board-wipes — wide decks can overwhelm you if you can\'t wipe the board. Look for 2-3 sweepers minimum.' },
      { role: 'draw', min: 8, message: 'Low card draw — control decks need to draw more cards than everyone else to win. Prioritize draw effects above all.' },
    ],
  },

  {
    ids: ['tempo', 'midrange', 'value'],
    macroPlan: 'Develop a balanced board with ramp and threats, answer key opposing plays, and close with your best cards.',
    howItWins: 'You win through card quality — your best cards are better than opponents\' best cards. With enough ramp and card draw, you find your threats reliably and deploy them with answers in hand.',
    earlyGame: 'Play a ramp spell early. Set up your mana base so you can deploy your best threats on time. Answer creatures that would get out of hand if left alone.',
    midGame: 'Develop your board while staying interactive. Look for opportunities to use your best cards efficiently. Your card draw should be keeping your hand stocked.',
    lateGame: 'Deploy your most powerful threats and protect them. You should have enough card advantage to reload after each exchange.',
    keepHandsWith: [
      'At least 3 lands with your commander\'s colors',
      'At least one ramp spell or early play',
      'A draw spell or something to find your threats',
    ],
    mulliganIf: 'You have no play before turn 3 and no way to find one. Slow starts fall too far behind.',
    interactionAdvice: 'Answer the most dangerous cards opponents play, not the first ones. Your interaction is limited — make each piece count.',
    commonMistakes: [
      'Not ramping in the early turns — every missed ramp opportunity delays your threats',
      'Using interaction too early on small threats instead of saving it for key cards',
      'Not attacking when the board is favorable — tempo is a resource',
    ],
    roleWarnings: [
      { role: 'ramp', min: 5, message: 'Low ramp — midrange decks need reliable mana acceleration to deploy threats on time.' },
      { role: 'draw', min: 6, message: 'Low card draw — you may run out of cards mid-game. Prioritize draw effects to stay in the game.' },
    ],
  },
];

// ── Template lookup ────────────────────────────────────────────────────────────

const TEMPLATE_BY_ID = new Map<string, StrategyTemplate>();
for (const t of STRATEGY_TEMPLATES) {
  for (const id of t.ids) {
    TEMPLATE_BY_ID.set(id, t);
  }
}

function getTemplate(strategyId: string): StrategyTemplate {
  return TEMPLATE_BY_ID.get(strategyId) ?? TEMPLATE_BY_ID.get('midrange')!;
}

// ── Fit badge ─────────────────────────────────────────────────────────────────

function fitBadge(score: number): FitBadge {
  if (score >= 68) return 'Recommended';
  if (score >= 48) return 'Viable';
  return 'Experimental';
}

// ── Mulligan scoring ──────────────────────────────────────────────────────────

function mulliganScoreSummary(roleCounts: Record<string, number>, strategyId: string): string {
  const draw = roleCounts['draw'] ?? 0;
  const ramp = roleCounts['ramp'] ?? 0;
  const interaction = (roleCounts['interaction'] ?? 0) + (roleCounts['counterspell'] ?? 0);
  const selection = roleCounts['selection'] ?? 0;

  let score = 0;
  if (ramp >= 5) score += 2;
  if (draw >= 8) score += 2;
  if (interaction >= 12) score += 2;
  if (selection >= 5) score += 1;

  // Strategy bonus
  if (strategyId === 'spellslinger_tempo' || strategyId === 'talion_control' || strategyId === 'control') {
    const cs = roleCounts['counterspell'] ?? 0;
    if (cs >= 7) score += 1;
  }
  if (strategyId === 'yuriko_tempo' || strategyId === 'satoru_toolbox' || strategyId === 'yuffie_ninjutsu') {
    const evasive = roleCounts['evasive_enabler'] ?? 0;
    if (evasive >= 12) score += 1;
  }

  const total = draw + ramp + interaction + selection;
  const frac = (total / 60) * 100;
  const pct = Math.min(frac, 40).toFixed(0);

  if (score >= 6) return `Strong deck. About ${pct}% of non-land cards are high-priority keeps — you will frequently see multiple good pieces in your opening 7.`;
  if (score >= 4) return `Solid deck. You have a good density of role cards. Most 7-card hands with 3 lands will have at least one or two key pieces.`;
  if (score >= 2) return `Functional deck. Your key piece density is moderate — you may need to mulligan once or twice to find the right mix.`;
  return `Lean deck. Keep hands that have your core pieces, and mulligan aggressively if you don\'t see interaction and a threat.`;
}

// ── Warning generation ─────────────────────────────────────────────────────────

function buildWarnings(roleCounts: Record<string, number>, template: StrategyTemplate): string[] {
  const warnings: string[] = [];
  for (const rw of template.roleWarnings) {
    const count = roleCounts[rw.role] ?? 0;
    if (count < rw.min) {
      warnings.push(rw.message);
    }
  }
  return warnings;
}

// ── Guide assembly ─────────────────────────────────────────────────────────────

export function generatePlayGuide(variant: DeckVariant): PlayGuide {
  const template = getTemplate(variant.strategyId);
  const warnings = buildWarnings(variant.roleCounts, template);
  const badge = fitBadge(variant.score);
  const scoreSummary = mulliganScoreSummary(variant.roleCounts, variant.strategyId);

  const fc: FeaturedCards = variant.featuredCards;

  return {
    commanderName: variant.commander.name,
    strategyName: variant.strategyName,
    fitBadge: badge,
    macroPlan: template.macroPlan,
    howItWins: template.howItWins,
    earlyGame: template.earlyGame,
    midGame: template.midGame,
    lateGame: template.lateGame,
    mulligan: {
      keepHandsWith: template.keepHandsWith,
      mulliganIf: template.mulliganIf,
      scoreSummary,
    },
    keyEngines: fc.engines,
    keyFinishers: fc.finishers,
    keyInteraction: fc.interaction,
    keyProtection: fc.protection,
    keySetup: fc.setup,
    keyRamp: fc.ramp,
    interactionAdvice: template.interactionAdvice,
    commonMistakes: template.commonMistakes,
    warnings,
  };
}
