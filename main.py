import random
from dataclasses import dataclass, field


RARITY_WEIGHTS = {
    "SSR": 5,
    "SR": 25,
    "R": 70,
}

RARITY_POWER = {
    "SSR": 42,
    "SR": 28,
    "R": 18,
}

ELEMENTS = ["火", "水", "雷", "风", "光", "暗"]

NAMES = [
    "林澈", "苏遥", "白夜", "周岚", "程星", "沈烬", "顾言", "叶汐", "韩朔", "唐璃",
    "许燃", "江黎", "傅青", "陆霜", "姜野", "宁歌", "秦烁", "莫离", "温羽", "洛尘",
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

    def team_power(self) -> int:
        top_three = sorted(self.roster, key=lambda c: c.power, reverse=True)[:3]
        return sum(c.power for c in top_three)


class Game:
    def __init__(self):
        self.player = Player()
        self.player.roster.extend([self._generate_card(guaranteed="SR") for _ in range(3)])

    def _generate_card(self, guaranteed: str | None = None) -> Card:
        rarity = guaranteed or random.choices(
            list(RARITY_WEIGHTS.keys()),
            weights=list(RARITY_WEIGHTS.values()),
            k=1,
        )[0]
        name = random.choice(NAMES)
        element = random.choice(ELEMENTS)
        return Card(name=name, rarity=rarity, element=element)

    def gacha_once(self) -> None:
        cost = 120
        if self.player.gems < cost:
            print("钻石不足，无法抽卡。")
            return
        self.player.gems -= cost
        card = self._generate_card()
        self.player.roster.append(card)
        print(f"获得角色：{card.rarity} {card.name}[{card.element}] 战力{card.power}")

    def gacha_ten(self) -> None:
        cost = 1080
        if self.player.gems < cost:
            print("钻石不足，无法十连。")
            return
        self.player.gems -= cost
        print("=== 十连抽卡 ===")
        has_sr_or_higher = False
        for i in range(10):
            card = self._generate_card()
            if i == 9 and not has_sr_or_higher:
                card = self._generate_card(guaranteed="SR")
            if card.rarity in ("SR", "SSR"):
                has_sr_or_higher = True
            self.player.roster.append(card)
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

    def battle_stage(self) -> None:
        if self.player.energy <= 0:
            print("体力不足，请稍后恢复。")
            return
        self.player.energy -= 1

        enemy_power = 80 + self.player.chapter * 24 + self.player.stage * 18
        team_power = self.player.team_power()
        print(f"出战战力：{team_power} | 敌方战力：{enemy_power}")

        win_chance = min(0.92, max(0.1, 0.45 + (team_power - enemy_power) / 220))
        if random.random() < win_chance:
            gain_coin = 180 + self.player.stage * 30
            gain_gem = 20 if self.player.stage % 3 == 0 else 10
            self.player.coins += gain_coin
            self.player.gems += gain_gem
            print(f"战斗胜利！获得 {gain_coin}金币 + {gain_gem}钻石")
            self.player.stage += 1
            if self.player.stage > 10:
                self.player.stage = 1
                self.player.chapter += 1
                print(f"章节突破！进入第 {self.player.chapter} 章")
        else:
            print("战斗失败，本次无奖励。建议提升角色等级或抽取更高稀有度角色。")

    def recover_energy(self) -> None:
        if self.player.gems < 50:
            print("钻石不足，无法恢复体力。")
            return
        self.player.gems -= 50
        self.player.energy = min(12, self.player.energy + 6)
        print(f"体力恢复成功，当前体力：{self.player.energy}")

    def show_status(self) -> None:
        print("\n=== 玩家状态 ===")
        print(
            f"章节: {self.player.chapter}-{self.player.stage} | 钻石: {self.player.gems} | 金币: {self.player.coins} | 体力: {self.player.energy}"
        )
        print(f"角色数: {len(self.player.roster)} | 主力队战力: {self.player.team_power()}")

    def show_roster(self) -> None:
        print("\n=== 角色列表 ===")
        for i, c in enumerate(self.player.roster, start=1):
            print(f"{i:02d}. {c.rarity} {c.name}[{c.element}] Lv.{c.level} 战力{c.power}")

    def run(self) -> None:
        print("欢迎来到《校园异能扭蛋》MVP 文字版！")
        while True:
            self.show_status()
            print(
                "\n1. 单抽(120钻)  2. 十连(1080钻)  3. 推进主线(消耗1体力)\n"
                "4. 升级角色      5. 查看角色      6. 恢复体力(50钻+6体力)\n"
                "7. 退出"
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
                print("感谢游玩，欢迎下次回来抽卡！")
                break
            else:
                print("无效输入，请重新选择。")


if __name__ == "__main__":
    random.seed()
    Game().run()
