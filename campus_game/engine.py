import json
import random
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List

from campus_game.content_database import (
    CARD_POOL,
    CHAPTER_BLUEPRINTS,
    ENEMY_POOL,
    EVENT_POOL,
    SKILL_POOL,
)
from . import ui

SAVE_PATH = Path("save_data.json")

RARITY_RATE = {"SSR": 0.05, "SR": 0.25, "R": 0.70}
RARITY_BASE = {"SSR": 52, "SR": 34, "R": 22}
RARITY_GROWTH = {"SSR": 6, "SR": 5, "R": 4}

RELIC_POOL = [
    {"id": "RLC001", "name": "炎纹芯片", "role": "强袭", "value": 0.12},
    {"id": "RLC002", "name": "潮汐芯片", "role": "术师", "value": 0.11},
    {"id": "RLC003", "name": "雷相芯片", "role": "狙击", "value": 0.13},
    {"id": "RLC004", "name": "岚盾芯片", "role": "守卫", "value": 0.12},
    {"id": "RLC005", "name": "光导芯片", "role": "支援", "value": 0.10},
    {"id": "RLC006", "name": "影袭芯片", "role": "先锋", "value": 0.11},
]


@dataclass
class Hero:
    hero_id: str
    name: str
    rarity: str
    element: str
    role: str
    skill_key: str
    level: int = 1
    star: int = 1
    exp: int = 0

    @property
    def power(self) -> int:
        base = RARITY_BASE[self.rarity] + self.level * RARITY_GROWTH[self.rarity]
        return int(base * (1 + 0.08 * (self.star - 1)))


@dataclass
class PlayerState:
    name: str = "代理班长"
    gems: int = 2200
    coins: int = 8000
    stamina: int = 20
    chapter: int = 1
    stage: int = 1
    account_level: int = 1
    account_exp: int = 0
    pity_count: int = 0
    trial_tickets: int = 3
    relic_shards: int = 0
    heroes: List[Dict] = field(default_factory=list)
    team_ids: List[str] = field(default_factory=list)
    hero_relics: Dict[str, Dict] = field(default_factory=dict)
    active_buffs: List[Dict] = field(default_factory=list)
    daily: Dict = field(default_factory=lambda: {
        "pull": 0,
        "battle": 0,
        "event": 0,
        "trial": 0,
        "claim": False,
    })
    quests: Dict[str, Dict] = field(default_factory=dict)


class GameEngine:
    def __init__(self):
        self.state = PlayerState()
        self.hero_dict: Dict[str, Hero] = {}
        self._bootstrap_new_account()
        self._ensure_quests()

    def _bootstrap_new_account(self):
        starter_ids = ["C0001", "C0002", "C0003"]
        for sid in starter_ids:
            card = next(c for c in CARD_POOL if c["id"] == sid)
            hero = Hero(
                hero_id=card["id"],
                name=card["name"],
                rarity=card["rarity"],
                element=card["element"],
                role=card["role"],
                skill_key=card["skill_key"],
            )
            self.hero_dict[hero.hero_id] = hero
        self.state.team_ids = starter_ids.copy()

    def _serialize(self) -> Dict:
        st = asdict(self.state)
        st["heroes"] = [asdict(h) for h in self.hero_dict.values()]
        return st

    def _hydrate(self, payload: Dict):
        self.state = PlayerState(**{k: v for k, v in payload.items() if k != "heroes"})
        self.hero_dict = {}
        for h in payload.get("heroes", []):
            hero = Hero(**h)
            self.hero_dict[hero.hero_id] = hero

    def save(self):
        SAVE_PATH.write_text(json.dumps(self._serialize(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已保存进度到 {SAVE_PATH}")

    def load(self):
        if not SAVE_PATH.exists():
            print("没有检测到存档，将继续当前新账号。")
            return
        payload = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
        self._hydrate(payload)
        self._ensure_quests()
        print("存档加载成功。")

    def _ensure_quests(self):
        for q in CHAPTER_BLUEPRINTS:
            qid = q["quest_id"]
            self.state.quests.setdefault(qid, {"progress": 0, "done": False, "claimed": False})

    def _get_team(self) -> List[Hero]:
        team = [self.hero_dict[i] for i in self.state.team_ids if i in self.hero_dict]
        if len(team) < 3:
            team = sorted(self.hero_dict.values(), key=lambda x: x.power, reverse=True)[:3]
        return team

    def _relic_bonus(self, hero: Hero) -> float:
        record = self.state.hero_relics.get(hero.hero_id)
        if not record:
            return 0.0
        bonus = record["value"]
        if record["role"] == hero.role:
            bonus += 0.04
        return bonus

    def _team_synergy_bonus(self, team: List[Hero]) -> float:
        roles = {h.role for h in team}
        elements = {h.element for h in team}
        bonus = 0.0
        if len(roles) == 3:
            bonus += 0.06
        if len(elements) == 3:
            bonus += 0.06
        return bonus

    def _skill_multiplier(self, hero: Hero, enemy: Dict) -> float:
        skill = SKILL_POOL[hero.skill_key]
        mult = 1.0
        if skill["trigger"] == "counter" and skill["target_element"] == enemy["element"]:
            mult += skill["value"]
        elif skill["trigger"] == "boss" and enemy["rank"] == "Boss":
            mult += skill["value"]
        elif skill["trigger"] == "elite" and enemy["rank"] == "Elite":
            mult += skill["value"]
        elif skill["trigger"] == "always":
            mult += skill["value"]
        return mult

    def _enemy_for_stage(self) -> Dict:
        c, s = self.state.chapter, self.state.stage
        chapter_def = CHAPTER_BLUEPRINTS[(c - 1) % len(CHAPTER_BLUEPRINTS)]
        if s == 10:
            rank = "Boss"
            multiplier = 1.45
        elif s in (5, 9):
            rank = "Elite"
            multiplier = 1.2
        else:
            rank = "Normal"
            multiplier = 1.0

        preferred = chapter_def["main_element"]
        chosen_pool = [e for e in ENEMY_POOL if e["element"] == preferred]
        other_pool = [e for e in ENEMY_POOL if e["element"] != preferred]
        template = random.choice(chosen_pool if random.random() < 0.72 else other_pool)

        level = c * 6 + s * 3
        base = template["base_power"] + level * 3 + c * 16 + s * 9
        return {
            "name": template["name"],
            "element": template["element"],
            "rank": rank,
            "level": level,
            "power": int(base * multiplier),
            "chapter_tag": chapter_def["chapter_title"],
        }

    def _trial_enemy(self, floor: int) -> Dict:
        template = random.choice(ENEMY_POOL)
        rank = "Boss" if floor % 3 == 0 else "Elite" if floor % 2 == 0 else "Normal"
        mult = 1.48 if rank == "Boss" else 1.22 if rank == "Elite" else 1.0
        level = self.state.chapter * 8 + floor * 4
        power = int((template["base_power"] + level * 4 + self.state.account_level * 6) * mult)
        return {
            "name": template["name"],
            "element": template["element"],
            "rank": rank,
            "level": level,
            "power": power,
            "chapter_tag": "深渊试炼",
        }

    def _team_power_detail(self, enemy: Dict):
        team = self._get_team()
        synergy = self._team_synergy_bonus(team)
        buff_mult = self._active_buff_multiplier()
        total = 0
        detail = []
        for h in team:
            mult = self._skill_multiplier(h, enemy)
            relic = self._relic_bonus(h)
            value = int(h.power * mult * (1 + relic) * buff_mult)
            total += value
            detail.append((h, mult, relic, value))
        total = int(total * (1 + synergy))
        return total, detail, synergy, buff_mult

    def _active_buff_multiplier(self) -> float:
        if not self.state.active_buffs:
            return 1.0
        total = sum(b["value"] for b in self.state.active_buffs if b.get("duration", 0) > 0)
        return 1.0 + total

    def _consume_buff_duration(self):
        if not self.state.active_buffs:
            return
        for buff in self.state.active_buffs:
            buff["duration"] = max(0, buff["duration"] - 1)
        self.state.active_buffs = [b for b in self.state.active_buffs if b["duration"] > 0]

    def _grant_account_exp(self, value: int):
        self.state.account_exp += value
        while self.state.account_exp >= self._account_level_cap(self.state.account_level):
            self.state.account_exp -= self._account_level_cap(self.state.account_level)
            self.state.account_level += 1
            self.state.stamina = min(35 + self.state.account_level, self.state.stamina + 3)
            self.state.trial_tickets = min(5, self.state.trial_tickets + 1)
            self.state.gems += 80
            print(f"账号升级到 Lv.{self.state.account_level}，奖励 80 钻石，体力+3，试炼票+1")

    @staticmethod
    def _account_level_cap(level: int) -> int:
        return 100 + level * 22

    def show_dashboard(self):
        team_power = sum(h.power for h in self._get_team())
        print("\n" + ui.title("校园异能扭蛋 - Playable++"))
        print(
            ui.kv(
                [
                    ("玩家", f"{self.state.name}"),
                    ("等级", f"Lv.{self.state.account_level}"),
                    ("经验", ui.progress(self.state.account_exp, self._account_level_cap(self.state.account_level), 12)),
                    ("章节", f"{self.state.chapter}-{self.state.stage}"),
                ]
            )
        )
        print(
            ui.kv(
                [
                    ("钻石", str(self.state.gems)),
                    ("金币", str(self.state.coins)),
                    ("体力", str(self.state.stamina)),
                    ("试炼票", str(self.state.trial_tickets)),
                    ("碎片", str(self.state.relic_shards)),
                    ("队伍战力", str(team_power)),
                ]
            )
        )
        if self.state.active_buffs:
            buff_text = ", ".join([f"{b['name']}(+{int(b['value']*100)}%, 剩{b['duration']}战)" for b in self.state.active_buffs])
            print(ui.color(f"当前增益: {buff_text}", "blue", bold=True))
        d = self.state.daily
        print(
            f"每日任务: 抽卡 {ui.progress(d['pull'], 5, 8)} "
            f"推图 {ui.progress(d['battle'], 4, 8)} "
            f"事件 {ui.progress(d['event'], 2, 8)} "
            f"试炼 {ui.progress(d['trial'], 1, 8)} "
            f"已领奖:{d['claim']}"
        )

    def pull_once(self):
        if self.state.gems < 120:
            print("钻石不足")
            return
        self.state.gems -= 120
        self.state.pity_count += 1
        hero = self._draw_hero()
        self._obtain_hero(hero)
        self.state.daily["pull"] += 1
        print(
            f"单抽获得: {ui.rarity(hero.rarity, hero.rarity)} "
            f"{hero.name}[{hero.element}/{hero.role}] 技能:{SKILL_POOL[hero.skill_key]['name']}"
        )

    def pull_ten(self):
        if self.state.gems < 1080:
            print("钻石不足")
            return
        self.state.gems -= 1080
        print(ui.section("=== 十连结果 ==="))
        got_sr_plus = False
        for idx in range(10):
            self.state.pity_count += 1
            hero = self._draw_hero(force_sr=(idx == 9 and not got_sr_plus))
            if hero.rarity in ("SR", "SSR"):
                got_sr_plus = True
            self._obtain_hero(hero)
            self.state.daily["pull"] += 1
            print(
                f"{idx + 1:02d}. {ui.rarity(hero.rarity, hero.rarity)} "
                f"{hero.name}[{hero.element}/{hero.role}] {SKILL_POOL[hero.skill_key]['name']}"
            )

    def _draw_hero(self, force_sr: bool = False) -> Hero:
        if self.state.pity_count >= 70:
            rarity = "SSR"
            self.state.pity_count = 0
        else:
            if force_sr:
                rarity = random.choice(["SR", "SSR"])
            else:
                roll = random.random()
                if roll < RARITY_RATE["SSR"]:
                    rarity = "SSR"
                    self.state.pity_count = 0
                elif roll < RARITY_RATE["SSR"] + RARITY_RATE["SR"]:
                    rarity = "SR"
                else:
                    rarity = "R"
        pool = [c for c in CARD_POOL if c["rarity"] == rarity]
        card = random.choice(pool)
        return Hero(
            hero_id=card["id"],
            name=card["name"],
            rarity=card["rarity"],
            element=card["element"],
            role=card["role"],
            skill_key=card["skill_key"],
        )

    def _obtain_hero(self, incoming: Hero):
        if incoming.hero_id in self.hero_dict:
            hero = self.hero_dict[incoming.hero_id]
            hero.exp += 20
            self.state.relic_shards += 4
            if hero.exp >= 100:
                hero.exp -= 100
                hero.star = min(6, hero.star + 1)
                print(f"  -> 重复角色转化，{hero.name} 升至 {hero.star} 星")
        else:
            self.hero_dict[incoming.hero_id] = incoming

    def roster(self):
        print(ui.section("=== 角色仓库 ==="))
        heroes = sorted(self.hero_dict.values(), key=lambda x: (x.rarity, x.power), reverse=True)
        for i, h in enumerate(heroes, start=1):
            sk = SKILL_POOL[h.skill_key]
            relic = self.state.hero_relics.get(h.hero_id)
            relic_txt = f" 芯片:{relic['name']}+{int(relic['value']*100)}%" if relic else ""
            print(
                f"{i:03d}. {h.hero_id} {h.rarity} {h.name}[{h.element}/{h.role}] Lv.{h.level} {h.star}★ 战力{h.power} "
                f"技能:{sk['name']}({sk['desc']}){relic_txt}"
            )

    def team_setup(self):
        ids = input("输入3个hero_id（空格分隔，如 C0001 C0002 C0003）: ").strip().split()
        if len(ids) != 3 or any(i not in self.hero_dict for i in ids):
            print("输入无效或角色不存在")
            return
        if len(set(ids)) != 3:
            print("不能重复选择")
            return
        self.state.team_ids = ids
        print("编队完成")

    def hero_upgrade(self):
        hero_id = input("输入要升级的hero_id: ").strip()
        if hero_id not in self.hero_dict:
            print("角色不存在")
            return
        hero = self.hero_dict[hero_id]
        cost = 240 + hero.level * 70
        if self.state.coins < cost:
            print(f"金币不足，需要 {cost}")
            return
        self.state.coins -= cost
        hero.level += 1
        self._grant_account_exp(20)
        print(f"{hero.name} 升级到 Lv.{hero.level}, 战力 {hero.power}")

    def relic_workshop(self):
        print(ui.section("=== 芯片工坊 ==="))
        print(f"当前碎片: {self.state.relic_shards} | 合成1个芯片需要 20碎片 + 800金币")
        print("1) 合成芯片  2) 装配芯片  3) 卸下芯片  0) 返回")
        choice = input("选择: ").strip()
        if choice == "1":
            if self.state.relic_shards < 20 or self.state.coins < 800:
                print("材料不足")
                return
            self.state.relic_shards -= 20
            self.state.coins -= 800
            relic = random.choice(RELIC_POOL)
            print(f"合成成功：{relic['name']}（适配{relic['role']}，+{int(relic['value']*100)}%）")
            target = input("输入要装配的hero_id(回车跳过): ").strip()
            if target and target in self.hero_dict:
                self.state.hero_relics[target] = relic
                print("装配成功")
        elif choice == "2":
            target = input("输入hero_id: ").strip()
            if target not in self.hero_dict:
                print("角色不存在")
                return
            for i, r in enumerate(RELIC_POOL, 1):
                print(f"{i}. {r['name']} 适配{r['role']} +{int(r['value']*100)}%")
            pick = input("输入编号装配(仅测试环境，不消耗): ").strip()
            if not pick.isdigit() or not (1 <= int(pick) <= len(RELIC_POOL)):
                print("输入无效")
                return
            self.state.hero_relics[target] = RELIC_POOL[int(pick) - 1]
            print("装配完成")
        elif choice == "3":
            target = input("输入hero_id: ").strip()
            if target in self.state.hero_relics:
                self.state.hero_relics.pop(target)
                print("已卸下")
            else:
                print("该角色无芯片")

    def battle(self):
        if self.state.stamina <= 0:
            print("体力不足")
            return
        self.state.stamina -= 1

        enemy = self._enemy_for_stage()
        team_power, detail, synergy, buff_mult = self._team_power_detail(enemy)

        print(
            ui.card_block(
                name=ui.rank(enemy["rank"], enemy["rank"]),
                subtitle=f"{enemy['name']} [{enemy['element']}] Lv.{enemy['level']}",
                lines=[
                    f"战力: {enemy['power']}",
                    f"区域: {enemy['chapter_tag']}",
                ],
            )
        )
        for h, m, relic, v in detail:
            print(f"  - {h.name} {h.element}/{h.role} 基础{h.power} 技能x{m:.2f} 芯片+{int(relic*100)}% => {v}")
        if synergy > 0:
            print(f"队伍协同加成 +{int(synergy*100)}%")
        if buff_mult > 1.0:
            print(f"远征增益加成 +{int((buff_mult-1)*100)}%")

        win_rate = max(0.08, min(0.95, 0.48 + (team_power - enemy['power']) / 360))
        print(f"总战力:{team_power}, 预计胜率:{ui.color(str(int(win_rate * 100)) + '%', 'green' if win_rate >= 0.5 else 'red', bold=True)}")

        if random.random() < win_rate:
            base_coin = 240 + self.state.chapter * 60 + self.state.stage * 35
            bonus = 180 if enemy["rank"] == "Elite" else 320 if enemy["rank"] == "Boss" else 0
            coin = base_coin + bonus
            gem = 12 if enemy["rank"] == "Normal" else 24 if enemy["rank"] == "Elite" else 45
            shard = 6 if enemy["rank"] == "Normal" else 12 if enemy["rank"] == "Elite" else 20
            self.state.coins += coin
            self.state.gems += gem
            self.state.relic_shards += shard
            self.state.daily["battle"] += 1
            self._grant_account_exp(28)
            self._advance_stage()
            self._quest_progress(1)
            self._consume_buff_duration()
            print(f"战斗胜利 +{coin}金币 +{gem}钻石 +{shard}芯片碎片")
        else:
            reason = self._battle_failure_advice(enemy)
            self._consume_buff_duration()
            print("战斗失败。建议：")
            for line in reason:
                print(f"  * {line}")

    def _battle_failure_advice(self, enemy: Dict):
        advice = []
        team = self._get_team()
        counters = [h for h in team if SKILL_POOL[h.skill_key]["target_element"] == enemy["element"]]
        if not counters:
            advice.append(f"当前缺少克制 {enemy['element']} 的技能角色，建议调整编队。")
        low = [h for h in team if h.level < self.state.chapter + 1]
        if low:
            advice.append("队伍平均等级偏低，建议至少提升主力到当前章节+1。")
        if all(h.hero_id not in self.state.hero_relics for h in team):
            advice.append("尝试在芯片工坊装配芯片，可显著提升战力。")
        advice.append("可先刷校园事件与试炼补资源，再回头推进主线。")
        return advice

    def abyss_trial(self):
        if self.state.trial_tickets <= 0:
            print("试炼票不足")
            return
        self.state.trial_tickets -= 1
        print(ui.section("=== 深渊试炼开始（3层）==="))
        total_score = 0
        for floor in range(1, 4):
            enemy = self._trial_enemy(floor)
            team_power, detail, synergy, buff_mult = self._team_power_detail(enemy)
            floor_rate = max(0.06, min(0.92, 0.45 + (team_power - enemy["power"]) / 390))
            print(f"第{floor}层: {enemy['name']} {enemy['rank']} Lv.{enemy['level']} 战力{enemy['power']} 胜率{int(floor_rate*100)}%")
            if buff_mult > 1.0:
                print(f"  增益生效 +{int((buff_mult-1)*100)}%")
            if random.random() < floor_rate:
                gained = int(enemy["power"] * 0.08)
                total_score += gained
                print(f"  胜利，获得试炼分 {gained}")
            else:
                print("  失败，本次试炼提前结束")
                break
            self._consume_buff_duration()
        coin = 300 + total_score // 2
        gem = 20 + total_score // 90
        shard = 10 + total_score // 140
        self.state.coins += coin
        self.state.gems += gem
        self.state.relic_shards += shard
        self.state.daily["trial"] += 1
        self._grant_account_exp(20)
        print(
            ui.card_block(
                name="试炼结算",
                subtitle=f"总分 {total_score}",
                lines=[f"金币 +{coin}", f"钻石 +{gem}", f"碎片 +{shard}"],
                width=42,
            )
        )

    def _advance_stage(self):
        self.state.stage += 1
        if self.state.stage > 10:
            self.state.stage = 1
            self.state.chapter += 1
            self.state.gems += 150
            print(f"章节突破，进入第 {self.state.chapter} 章，奖励 150 钻石")

    def campus_event(self):
        if self.state.stamina < 2:
            print("体力不足（事件需2体力）")
            return
        self.state.stamina -= 2
        event = random.choice(EVENT_POOL)
        print(f"\n事件: {event['title']} / 风险:{event['risk']} 预期收益:{event['reward_hint']}")
        print("1) 稳妥方案  2) 激进方案")
        pick = input("选择: ").strip()
        option = event["safe"] if pick == "1" else event["risky"] if pick == "2" else None
        if not option:
            print("犹豫错失机会，只获得 60 金币")
            self.state.coins += 60
            return
        if random.random() < option["success"]:
            self.state.coins += option["coin"]
            self.state.gems += option["gem"]
            self.state.relic_shards += 3
            self.state.daily["event"] += 1
            self._grant_account_exp(16)
            print(f"处理成功 +{option['coin']}金币 +{option['gem']}钻石 +3碎片")
        else:
            loss = option["penalty"]
            self.state.coins = max(0, self.state.coins - loss)
            print(f"处理失败，损失 {loss} 金币")

    def daily_center(self):
        d = self.state.daily
        print(f"抽卡{d['pull']}/5 推图{d['battle']}/4 事件{d['event']}/2 试炼{d['trial']}/1 已领奖:{d['claim']}")
        if d["pull"] >= 5 and d["battle"] >= 4 and d["event"] >= 2 and d["trial"] >= 1 and not d["claim"]:
            yn = input("可领取 420 钻石 + 2200 金币 + 35碎片，领取?(y/n): ").lower().strip()
            if yn == "y":
                d["claim"] = True
                self.state.gems += 420
                self.state.coins += 2200
                self.state.relic_shards += 35
                print("每日奖励领取成功")
        elif d["claim"]:
            print("今日已领取")
        else:
            print("继续完成任务")

    def quest_board(self):
        print(ui.section("=== 章节任务板 ==="))
        for q in CHAPTER_BLUEPRINTS:
            state = self.state.quests[q["quest_id"]]
            print(f"{q['quest_id']} {q['title']} 进度 {state['progress']}/{q['target']} 完成:{state['done']} 已领:{state['claimed']}")
        qid = input("输入任务ID领取奖励(或回车返回): ").strip()
        if not qid:
            return
        if qid not in self.state.quests:
            print("任务不存在")
            return
        qdef = next(q for q in CHAPTER_BLUEPRINTS if q["quest_id"] == qid)
        qst = self.state.quests[qid]
        if not qst["done"]:
            print("任务尚未完成")
            return
        if qst["claimed"]:
            print("奖励已领取")
            return
        qst["claimed"] = True
        self.state.coins += qdef["reward_coin"]
        self.state.gems += qdef["reward_gem"]
        self.state.relic_shards += 12
        print(f"领取成功 +{qdef['reward_coin']}金币 +{qdef['reward_gem']}钻石 +12碎片")

    def _quest_progress(self, amount: int):
        for q in CHAPTER_BLUEPRINTS:
            qst = self.state.quests[q["quest_id"]]
            if qst["done"]:
                continue
            qst["progress"] += amount
            if qst["progress"] >= q["target"]:
                qst["done"] = True
                print(f"任务完成：{q['title']}，请前往任务板领奖")
            break

    def chapter_planning(self):
        curr = self.state.chapter
        next_c = curr + 1
        curr_def = CHAPTER_BLUEPRINTS[(curr - 1) % len(CHAPTER_BLUEPRINTS)]
        next_def = CHAPTER_BLUEPRINTS[(next_c - 1) % len(CHAPTER_BLUEPRINTS)]
        sim_curr = self._simulate_enemy_power(curr, 6)
        sim_next = self._simulate_enemy_power(next_c, 3)
        team_power = sum(h.power * (1 + self._relic_bonus(h)) for h in self._get_team())
        print(ui.section("=== 章节规划 ==="))
        print(f"当前章({curr})主题:{curr_def['chapter_title']} 主属性:{curr_def['main_element']} 推荐克制:{curr_def['counter']}")
        print(f"下一章({next_c})主题:{next_def['chapter_title']} 主属性:{next_def['main_element']} 推荐克制:{next_def['counter']}")
        print(f"当前章中段参考敌战力:{sim_curr} | 下一章前段参考敌战力:{sim_next}")
        print(f"你当前队伍战力(含芯片):{int(team_power)}，建议达到下一章参考值的 90% 以上再冲关。")

    def mystery_expedition(self):
        if self.state.stamina < 3:
            print("体力不足（远征需3体力）")
            return
        self.state.stamina -= 3
        print(ui.section("=== 校园秘境远征（5节点）==="))
        buffs_found = []
        coin_gain = 0
        shard_gain = 0
        for step in range(1, 6):
            node = random.choice(["战斗", "补给", "奇遇"])
            print(f"节点{step}: {node}")
            if node == "战斗":
                enemy = self._trial_enemy(step + self.state.chapter)
                team_power, _, _, _ = self._team_power_detail(enemy)
                rate = max(0.1, min(0.92, 0.45 + (team_power - enemy['power']) / 420))
                print(f"  遭遇 {enemy['name']} ({enemy['rank']})，胜率{int(rate*100)}%")
                if random.random() < rate:
                    c = 120 + step * 40
                    s = 4 + step
                    coin_gain += c
                    shard_gain += s
                    print(f"  战斗胜利 +{c}金币 +{s}碎片")
                else:
                    loss = 80 + step * 20
                    self.state.coins = max(0, self.state.coins - loss)
                    print(f"  战斗失利，损失 {loss} 金币")
            elif node == "补给":
                self.state.stamina = min(45, self.state.stamina + 2)
                c = 180 + step * 30
                coin_gain += c
                print(f"  获得补给: +2体力 +{c}金币")
            else:
                buff = random.choice(
                    [
                        {"name": "斗志高昂", "value": 0.08, "duration": 3},
                        {"name": "元素共鸣", "value": 0.1, "duration": 2},
                        {"name": "战术冷静", "value": 0.06, "duration": 4},
                    ]
                )
                buffs_found.append(buff)
                print(f"  触发奇遇，获得增益 {buff['name']} +{int(buff['value']*100)}% 持续{buff['duration']}战")
        self.state.coins += coin_gain
        self.state.relic_shards += shard_gain
        self.state.active_buffs.extend(buffs_found)
        self.state.daily["event"] += 1
        self._grant_account_exp(24)
        print(ui.card_block("远征结算", f"获得增益{len(buffs_found)}个", [f"金币 +{coin_gain}", f"碎片 +{shard_gain}"], width=42))

    def _simulate_enemy_power(self, chapter: int, stage: int) -> int:
        level = chapter * 6 + stage * 3
        base = 95 + chapter * 16 + stage * 9 + level * 3
        if stage == 10:
            return int(base * 1.45)
        if stage in (5, 9):
            return int(base * 1.2)
        return base

    def stamina_recover(self):
        if self.state.gems < 60:
            print("钻石不足")
            return
        self.state.gems -= 60
        self.state.stamina = min(45, self.state.stamina + 10)
        print(f"体力恢复完成，当前 {self.state.stamina}")

    def reset_daily(self):
        self.state.daily = {"pull": 0, "battle": 0, "event": 0, "trial": 0, "claim": False}
        self.state.trial_tickets = 3
        print("每日状态已重置（用于本地测试）")

    def run(self):
        self.load()
        while True:
            self.show_dashboard()
            print(
                ui.menu_block(
                    [
                        "1 单抽      2 十连      3 推图      4 校园事件",
                        "5 角色仓库  6 编队      7 角色升级  8 每日任务",
                        "9 章节任务板 10 章节规划 11 体力恢复 12 保存",
                        "13 重置每日(测试) 14 芯片工坊 15 深渊试炼 16 秘境远征",
                        "0 退出",
                    ]
                )
            )
            choice = input("选择操作: ").strip()
            if choice == "1":
                self.pull_once()
            elif choice == "2":
                self.pull_ten()
            elif choice == "3":
                self.battle()
            elif choice == "4":
                self.campus_event()
            elif choice == "5":
                self.roster()
            elif choice == "6":
                self.team_setup()
            elif choice == "7":
                self.hero_upgrade()
            elif choice == "8":
                self.daily_center()
            elif choice == "9":
                self.quest_board()
            elif choice == "10":
                self.chapter_planning()
            elif choice == "11":
                self.stamina_recover()
            elif choice == "12":
                self.save()
            elif choice == "13":
                self.reset_daily()
            elif choice == "14":
                self.relic_workshop()
            elif choice == "15":
                self.abyss_trial()
            elif choice == "16":
                self.mystery_expedition()
            elif choice == "0":
                self.save()
                print("感谢游玩，已自动保存。")
                break
            else:
                print("无效输入")
