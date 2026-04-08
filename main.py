import random
from dataclasses import dataclass, field

RARITY_WEIGHTS = {"SSR": 5, "SR": 25, "R": 70}
RARITY_POWER = {"SSR": 42, "SR": 28, "R": 18}
ELEMENTS = ["火", "水", "雷", "风", "光", "暗"]
ELEMENT_COUNTER = {
    "火": "风",
    "风": "雷",
    "雷": "水",
    "水": "火",
    "光": "暗",
    "暗": "光",
}

NAMES = [
    "林澈", "苏遥", "白夜", "周岚", "程星", "沈烬", "顾言", "叶汐", "韩朔", "唐璃",
    "许燃", "江黎", "傅青", "陆霜", "姜野", "宁歌", "秦烁", "莫离", "温羽", "洛尘",
]

EVENTS = [
    {
        "title": "实验楼能量泄露",
        "options": [
            ("立即封锁区域", 0.75, 260, 15),
            ("尝试吸收异能", 0.45, 420, 35),
        ],
    },
    {
        "title": "社团竞赛突发袭击",
        "options": [
            ("稳妥掩护撤离", 0.80, 220, 15),
            ("正面硬刚首领", 0.48, 460, 40),
        ],
    },
    {
        "title": "旧校舍怪谈失控",
        "options": [
            ("调查并净化", 0.70, 300, 20),
            ("追踪源头核心", 0.40, 520, 45),
        ],
    },
]


@dataclass
class Card:
    name: str
    rarity: str
    element: str
    level: int = 1

    @property
    def power(self) -> int:
        return RARITY_POWER[self.rarity] + (self.level - 1) * 4


@dataclass
class Player:
    gems: int = 1200
    coins: int = 1000
    energy: int = 12
    chapter: int = 1
    stage: int = 1
    roster: list[Card] = field(default_factory=list)
    selected_team: list[int] = field(default_factory=list)

    def team_cards(self) -> list[Card]:
        if self.selected_team:
            valid = [i for i in self.selected_team if 0 <= i < len(self.roster)]
            cards = [self.roster[i] for i in valid]
            if cards:
                return cards
        return sorted(self.roster, key=lambda c: c.power, reverse=True)[:3]

    def team_power(self) -> int:
        return sum(c.power for c in self.team_cards())


@dataclass
class DailyMissions:
    pulls_target: int = 3
    stages_target: int = 2
    event_target: int = 1
    pulls_done: int = 0
    stages_done: int = 0
    event_done: int = 0
    claimed: bool = False

    def progress_text(self) -> str:
        return (
            f"抽卡 {self.pulls_done}/{self.pulls_target} | 推图 {self.stages_done}/{self.stages_target} | "
            f"校园事件 {self.event_done}/{self.event_target}"
        )

    def is_complete(self) -> bool:
        return (
            self.pulls_done >= self.pulls_target
            and self.stages_done >= self.stages_target
            and self.event_done >= self.event_target
        )


class Game:
    def __init__(self):
        self.player = Player()
        self.missions = DailyMissions()
        self.player.roster.extend([self._generate_card(guaranteed="SR") for _ in range(3)])

    def _generate_card(self, guaranteed: str | None = None) -> Card:
        rarity = guaranteed or random.choices(list(RARITY_WEIGHTS), weights=list(RARITY_WEIGHTS.values()), k=1)[0]
        return Card(name=random.choice(NAMES), rarity=rarity, element=random.choice(ELEMENTS))

    def _team_element_bonus(self, enemy_element: str) -> float:
        team = self.player.team_cards()
        bonus = 0.0
        counter_count = sum(1 for c in team if ELEMENT_COUNTER[c.element] == enemy_element)
        if counter_count >= 2:
            bonus += 0.12
        unique = {c.element for c in team}
        if len(unique) == 3:
            bonus += 0.06
        return bonus

    def gacha_once(self) -> None:
        if self.player.gems < 120:
            print("钻石不足，无法抽卡。")
            return
        self.player.gems -= 120
        card = self._generate_card()
        self.player.roster.append(card)
        self.missions.pulls_done += 1
        print(f"获得角色：{card.rarity} {card.name}[{card.element}] 战力{card.power}")

    def gacha_ten(self) -> None:
        if self.player.gems < 1080:
            print("钻石不足，无法十连。")
            return
        self.player.gems -= 1080
        print("=== 十连抽卡 ===")
        has_sr_or_higher = False
        for i in range(10):
            card = self._generate_card()
            if i == 9 and not has_sr_or_higher:
                card = self._generate_card(guaranteed="SR")
            if card.rarity in ("SR", "SSR"):
                has_sr_or_higher = True
            self.player.roster.append(card)
            self.missions.pulls_done += 1
            print(f"{i + 1:02d}. {card.rarity} {card.name}[{card.element}] 战力{card.power}")

    def upgrade_card(self) -> None:
        if not self.player.roster:
            print("暂无角色。")
            return
        self.show_roster()
        idx = input("输入要升级的角色编号：").strip()
        if not idx.isdigit():
            print("输入无效。")
            return
        i = int(idx) - 1
        if i < 0 or i >= len(self.player.roster):
            print("编号超出范围。")
            return
        card = self.player.roster[i]
        cost = 200 + card.level * 60
        if self.player.coins < cost:
            print(f"金币不足，升级需要{cost}金币。")
            return
        self.player.coins -= cost
        card.level += 1
        print(f"{card.name} 升到 Lv.{card.level}，战力提升到 {card.power}。")

    def set_team(self) -> None:
        if len(self.player.roster) < 3:
            print("角色不足3人，无法手动编队。")
            return
        self.show_roster()
        raw = input("输入3个角色编号（空格分隔），例如 1 3 5：").strip().split()
        if len(raw) != 3 or not all(x.isdigit() for x in raw):
            print("输入格式错误。")
            return
        ids = [int(x) - 1 for x in raw]
        if len(set(ids)) != 3 or any(i < 0 or i >= len(self.player.roster) for i in ids):
            print("编号重复或越界。")
            return
        self.player.selected_team = ids
        names = [self.player.roster[i].name for i in ids]
        print(f"编队成功：{' / '.join(names)}")

    def battle_stage(self) -> None:
        if self.player.energy <= 0:
            print("体力不足，请稍后恢复。")
            return
        self.player.energy -= 1

        enemy_element = random.choice(ELEMENTS)
        enemy_power = 80 + self.player.chapter * 24 + self.player.stage * 18
        team_power = self.player.team_power()
        element_bonus = self._team_element_bonus(enemy_element)

        print(f"敌方属性：{enemy_element} | 出战战力：{team_power} | 敌方战力：{enemy_power}")
        if element_bonus > 0:
            print(f"触发属性克制/阵容加成：+{int(element_bonus * 100)}%")

        adjusted_power = team_power * (1 + element_bonus)
        win_chance = min(0.92, max(0.12, 0.45 + (adjusted_power - enemy_power) / 220))

        if random.random() < win_chance:
            gain_coin = 180 + self.player.stage * 30
            gain_gem = 20 if self.player.stage % 3 == 0 else 10
            self.player.coins += gain_coin
            self.player.gems += gain_gem
            self.missions.stages_done += 1
            print(f"战斗胜利！获得 {gain_coin}金币 + {gain_gem}钻石")
            self.player.stage += 1
            if self.player.stage > 10:
                self.player.stage = 1
                self.player.chapter += 1
                print(f"章节突破！进入第 {self.player.chapter} 章")
        else:
            print("战斗失败，本次无奖励。建议调整编队属性或提升等级。")

    def campus_event(self) -> None:
        if self.player.energy < 2:
            print("体力不足（校园事件需要2体力）。")
            return
        event = random.choice(EVENTS)
        self.player.energy -= 2
        print(f"\n=== 校园突发事件：{event['title']} ===")
        for i, option in enumerate(event["options"], start=1):
            print(f"{i}. {option[0]}")
        choice = input("选择方案：").strip()
        if choice not in ("1", "2"):
            print("你犹豫不决，事件错失机会，仅获得50金币。")
            self.player.coins += 50
            return

        _, success_rate, coin_reward, gem_reward = event["options"][int(choice) - 1]
        if random.random() < success_rate:
            self.player.coins += coin_reward
            self.player.gems += gem_reward
            self.missions.event_done += 1
            print(f"处理成功！获得 {coin_reward}金币 + {gem_reward}钻石")
        else:
            penalty = random.randint(70, 160)
            self.player.coins = max(0, self.player.coins - penalty)
            print(f"处理失败，修复损失花费 {penalty} 金币。")

    def mission_center(self) -> None:
        print("\n=== 每日任务 ===")
        print(self.missions.progress_text())
        if self.missions.is_complete() and not self.missions.claimed:
            print("任务已完成，可领取奖励：300钻石 + 600金币")
            choose = input("是否领取？(y/n)：").strip().lower()
            if choose == "y":
                self.player.gems += 300
                self.player.coins += 600
                self.missions.claimed = True
                print("领取成功！")
        elif self.missions.claimed:
            print("今日奖励已领取。")
        else:
            print("继续完成任务目标吧。")

    def recover_energy(self) -> None:
        if self.player.gems < 50:
            print("钻石不足，无法恢复体力。")
            return
        self.player.gems -= 50
        self.player.energy = min(12, self.player.energy + 6)
        print(f"体力恢复成功，当前体力：{self.player.energy}")

    def show_status(self) -> None:
        print("\n=== 玩家状态 ===")
        print(f"章节: {self.player.chapter}-{self.player.stage} | 钻石: {self.player.gems} | 金币: {self.player.coins} | 体力: {self.player.energy}")
        print(f"角色数: {len(self.player.roster)} | 主力队战力: {self.player.team_power()} | 每日任务: {self.missions.progress_text()}")

    def show_roster(self) -> None:
        print("\n=== 角色列表 ===")
        for i, c in enumerate(self.player.roster, start=1):
            print(f"{i:02d}. {c.rarity} {c.name}[{c.element}] Lv.{c.level} 战力{c.power}")

    def run(self) -> None:
        print("欢迎来到《校园异能扭蛋》MVP+ 文字版！")
        while True:
            self.show_status()
            print(
                "\n1. 单抽(120钻)   2. 十连(1080钻)   3. 推进主线(1体力)\n"
                "4. 升级角色       5. 查看角色        6. 恢复体力(50钻+6体力)\n"
                "7. 校园事件(2体力) 8. 编队             9. 每日任务\n"
                "0. 退出"
            )
            choice = input("请选择操作：").strip()
            if choice == "1":
                self.gacha_once()
            elif choice == "2":
                self.gacha_ten()
            elif choice == "3":
                self.battle_stage()
            elif choice == "4":
                self.upgrade_card()
            elif choice == "5":
                self.show_roster()
            elif choice == "6":
                self.recover_energy()
            elif choice == "7":
                self.campus_event()
            elif choice == "8":
                self.set_team()
            elif choice == "9":
                self.mission_center()
            elif choice == "0":
                print("感谢游玩，欢迎下次回来抽卡！")
                break
            else:
                print("无效输入，请重新选择。")


if __name__ == "__main__":
    random.seed()
    Game().run()
