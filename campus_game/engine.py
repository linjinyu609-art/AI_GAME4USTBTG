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

SAVE_PATH = Path("save_data.json")

RARITY_RATE = {"SSR": 0.05, "SR": 0.25, "R": 0.70}
RARITY_BASE = {"SSR": 52, "SR": 34, "R": 22}
RARITY_GROWTH = {"SSR": 6, "SR": 5, "R": 4}


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
    heroes: List[Dict] = field(default_factory=list)
    team_ids: List[str] = field(default_factory=list)
    daily: Dict = field(default_factory=lambda: {
        "pull": 0,
        "battle": 0,
        "event": 0,
        "claim": False,
    })
    quests: Dict[str, Dict] = field(default_factory=dict)


class GameEngine:
    def __init__(self):
        self.state = PlayerState()
        self.hero_dict: Dict[str, Hero] = {}
        self._bootstrap_new_account()
        self._ensure_quests()

    # -------------------------- 生命周期 --------------------------
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

    # -------------------------- 数据与计算 --------------------------
    def _ensure_quests(self):
        for q in CHAPTER_BLUEPRINTS:
            qid = q["quest_id"]
            self.state.quests.setdefault(qid, {"progress": 0, "done": False, "claimed": False})

    def _get_team(self) -> List[Hero]:
        team = [self.hero_dict[i] for i in self.state.team_ids if i in self.hero_dict]
        if len(team) < 3:
            team = sorted(self.hero_dict.values(), key=lambda x: x.power, reverse=True)[:3]
        return team

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

    def _team_power_detail(self, enemy: Dict):
        team = self._get_team()
        total = 0
        detail = []
        for h in team:
            mult = self._skill_multiplier(h, enemy)
            value = int(h.power * mult)
            total += value
            detail.append((h, mult, value))
        return total, detail

    def _grant_account_exp(self, value: int):
        self.state.account_exp += value
        while self.state.account_exp >= self._account_level_cap(self.state.account_level):
            self.state.account_exp -= self._account_level_cap(self.state.account_level)
            self.state.account_level += 1
            self.state.stamina = min(30 + self.state.account_level, self.state.stamina + 3)
            self.state.gems += 80
            print(f"账号升级到 Lv.{self.state.account_level}，奖励 80 钻石，体力+3")

    @staticmethod
    def _account_level_cap(level: int) -> int:
        return 100 + level * 22

    # -------------------------- 核心功能 --------------------------
    def show_dashboard(self):
        team_power = sum(h.power for h in self._get_team())
        print("\n=== 校园异能扭蛋 - 可玩版 ===")
        print(
            f"玩家:{self.state.name} Lv.{self.state.account_level}({self.state.account_exp}/{self._account_level_cap(self.state.account_level)})"
            f" 章节:{self.state.chapter}-{self.state.stage}"
        )
        print(f"钻石:{self.state.gems} 金币:{self.state.coins} 体力:{self.state.stamina} 队伍基础战力:{team_power}")
        d = self.state.daily
        print(f"每日任务: 抽卡{d['pull']}/5 推图{d['battle']}/4 事件{d['event']}/2 已领奖:{d['claim']}")

    def pull_once(self):
        cost = 120
        if self.state.gems < cost:
            print("钻石不足")
            return
        self.state.gems -= cost
        self.state.pity_count += 1
        hero = self._draw_hero()
        self._obtain_hero(hero)
        self.state.daily["pull"] += 1
        print(f"单抽获得: {hero.rarity} {hero.name}[{hero.element}/{hero.role}] 技能:{SKILL_POOL[hero.skill_key]['name']}")

    def pull_ten(self):
        cost = 1080
        if self.state.gems < cost:
            print("钻石不足")
            return
        self.state.gems -= cost
        print("\n=== 十连结果 ===")
        got_sr_plus = False
        for idx in range(10):
            self.state.pity_count += 1
            hero = self._draw_hero(force_sr=(idx == 9 and not got_sr_plus))
            if hero.rarity in ("SR", "SSR"):
                got_sr_plus = True
            self._obtain_hero(hero)
            self.state.daily["pull"] += 1
            print(f"{idx + 1:02d}. {hero.rarity} {hero.name}[{hero.element}/{hero.role}] {SKILL_POOL[hero.skill_key]['name']}")

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
            if hero.exp >= 100:
                hero.exp -= 100
                hero.star = min(6, hero.star + 1)
                print(f"  -> 重复角色转化，{hero.name} 升至 {hero.star} 星")
        else:
            self.hero_dict[incoming.hero_id] = incoming

    def roster(self):
        print("\n=== 角色仓库 ===")
        heroes = sorted(self.hero_dict.values(), key=lambda x: (x.rarity, x.power), reverse=True)
        for i, h in enumerate(heroes, start=1):
            sk = SKILL_POOL[h.skill_key]
            print(
                f"{i:03d}. {h.hero_id} {h.rarity} {h.name}[{h.element}/{h.role}] Lv.{h.level} {h.star}★ 战力{h.power} "
                f"技能:{sk['name']}({sk['desc']})"
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

    def battle(self):
        if self.state.stamina <= 0:
            print("体力不足")
            return
        self.state.stamina -= 1

        enemy = self._enemy_for_stage()
        team_power, detail = self._team_power_detail(enemy)

        print(f"\n敌人: {enemy['name']} [{enemy['element']}] {enemy['rank']} Lv.{enemy['level']} 战力{enemy['power']} ({enemy['chapter_tag']})")
        for h, m, v in detail:
            print(f"  - {h.name} {h.element}/{h.role} 基础{h.power} 技能倍率x{m:.2f} => {v}")

        win_rate = max(0.08, min(0.95, 0.48 + (team_power - enemy["power"]) / 360))
        print(f"总战力:{team_power}, 预计胜率:{int(win_rate * 100)}%")

        if random.random() < win_rate:
            base_coin = 240 + self.state.chapter * 60 + self.state.stage * 35
            bonus = 180 if enemy["rank"] == "Elite" else 320 if enemy["rank"] == "Boss" else 0
            coin = base_coin + bonus
            gem = 12 if enemy["rank"] == "Normal" else 24 if enemy["rank"] == "Elite" else 45
            self.state.coins += coin
            self.state.gems += gem
            self.state.daily["battle"] += 1
            self._grant_account_exp(28)
            self._advance_stage()
            self._quest_progress(1)
            print(f"战斗胜利 +{coin}金币 +{gem}钻石")
        else:
            reason = self._battle_failure_advice(enemy, detail)
            print("战斗失败。建议：")
            for line in reason:
                print(f"  * {line}")

    def _battle_failure_advice(self, enemy: Dict, detail: List):
        advice = []
        team = self._get_team()
        missing = [h for h in team if SKILL_POOL[h.skill_key]["target_element"] == enemy["element"]]
        if not missing:
            advice.append(f"当前缺少克制 {enemy['element']} 的技能角色，建议调整编队。")
        low = [h for h in team if h.level < self.state.chapter + 1]
        if low:
            advice.append("队伍平均等级偏低，建议至少提升主力到当前章节+1。")
        advice.append("可先刷校园事件与任务补资源，再回头推进主线。")
        return advice

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
            self.state.daily["event"] += 1
            self._grant_account_exp(16)
            print(f"处理成功 +{option['coin']}金币 +{option['gem']}钻石")
        else:
            loss = option["penalty"]
            self.state.coins = max(0, self.state.coins - loss)
            print(f"处理失败，损失 {loss} 金币")

    def daily_center(self):
        d = self.state.daily
        print(f"抽卡{d['pull']}/5 推图{d['battle']}/4 事件{d['event']}/2 已领奖:{d['claim']}")
        if d["pull"] >= 5 and d["battle"] >= 4 and d["event"] >= 2 and not d["claim"]:
            yn = input("可领取 360 钻石 + 1800 金币，领取?(y/n): ").lower().strip()
            if yn == "y":
                d["claim"] = True
                self.state.gems += 360
                self.state.coins += 1800
                print("每日奖励领取成功")
        elif d["claim"]:
            print("今日已领取")
        else:
            print("继续完成任务")

    def quest_board(self):
        print("\n=== 章节任务板 ===")
        for q in CHAPTER_BLUEPRINTS:
            state = self.state.quests[q["quest_id"]]
            print(
                f"{q['quest_id']} {q['title']} 进度 {state['progress']}/{q['target']} 完成:{state['done']} 已领:{state['claimed']}"
            )
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
        print(f"领取成功 +{qdef['reward_coin']}金币 +{qdef['reward_gem']}钻石")

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
        team_power = sum(h.power for h in self._get_team())
        print("\n=== 章节规划 ===")
        print(f"当前章({curr})主题:{curr_def['chapter_title']} 主属性:{curr_def['main_element']} 推荐克制:{curr_def['counter']} ")
        print(f"下一章({next_c})主题:{next_def['chapter_title']} 主属性:{next_def['main_element']} 推荐克制:{next_def['counter']} ")
        print(f"当前章中段参考敌战力:{sim_curr} | 下一章前段参考敌战力:{sim_next}")
        print(f"你当前队伍战力:{team_power}，建议达到下一章参考值的 90% 以上再冲关。")

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
        self.state.stamina = min(40, self.state.stamina + 10)
        print(f"体力恢复完成，当前 {self.state.stamina}")

    def reset_daily(self):
        self.state.daily = {"pull": 0, "battle": 0, "event": 0, "claim": False}
        print("每日状态已重置（用于本地测试）")

    # -------------------------- 运行 --------------------------
    def run(self):
        self.load()
        while True:
            self.show_dashboard()
            print(
                "\n1单抽 2十连 3推图 4校园事件 5角色仓库 6编队 7角色升级 8每日任务"
                "\n9章节任务板 10章节规划 11体力恢复 12保存 13重置每日(测试) 0退出"
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
            elif choice == "0":
                self.save()
                print("感谢游玩，已自动保存。")
                break
            else:
                print("无效输入")
