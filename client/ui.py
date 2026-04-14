"""Модуль пользовательского интерфейса"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
import time

console = Console()


class GameUI:
    def __init__(self, state):
        self.state = state
        self.authenticated = False
        self.current_input = ""

        # Анимация глобального кулдауна
        self.cooldown_active = False
        self.cooldown_remaining = 0
        self.cooldown_start_time = 0
        self.animation_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.animation_index = 0

        # Кулдауны оружия
        self.weapon_cooldowns = {}  # {weapon: {"active": True, "remaining": 5, "start_time": timestamp}}

    def set_cooldown(self, remaining, message=""):
        """Установка глобального кулдауна"""
        self.cooldown_active = True
        self.cooldown_remaining = remaining
        self.cooldown_start_time = time.time()
        if message:
            self.state.add_log(f"[yellow]{message}[/yellow]")

    def set_weapon_cooldown(self, weapon, remaining, message=""):
        """Установка кулдауна оружия"""
        self.weapon_cooldowns[weapon] = {
            "active": True,
            "remaining": remaining,
            "start_time": time.time()
        }
        if message:
            self.state.add_log(f"[yellow]{message}[/yellow]")

    def get_cooldown_animation(self):
        """Возвращает анимированную строку для глобального кулдауна"""
        if not self.cooldown_active:
            return None

        elapsed = time.time() - self.cooldown_start_time
        remaining = max(0, self.cooldown_remaining - elapsed)

        if remaining <= 0:
            self.cooldown_active = False
            return None

        self.animation_index = (self.animation_index + 1) % len(self.animation_frames)
        spinner = self.animation_frames[self.animation_index]

        total = self.cooldown_remaining
        progress = int((total - remaining) / total * 20)
        bar = "█" * progress + "░" * (20 - progress)

        return f"{spinner} [yellow]КУЛДАУН: {bar} {remaining:.1f} сек[/yellow]"

    def get_weapon_cooldown_bar(self, weapon):
        """Возвращает строку с прогресс-баром для оружия"""
        if weapon not in self.weapon_cooldowns:
            return None

        cd = self.weapon_cooldowns[weapon]
        if not cd["active"]:
            return None

        elapsed = time.time() - cd["start_time"]
        remaining = max(0, cd["remaining"] - elapsed)

        if remaining <= 0:
            del self.weapon_cooldowns[weapon]
            return None

        total = cd["remaining"]
        progress = int((total - remaining) / total * 10)
        bar = "█" * progress + "░" * (10 - progress)

        return f"[dim]{bar} {remaining:.1f}с[/dim]"

    def draw_layout(self):
        """Отрисовка основного интерфейса"""
        layout = Layout()
        layout.split_column(
            Layout(name="top", size=6),
            Layout(name="middle", size=15),
            Layout(name="bottom", size=9),
            Layout(name="input", size=3)
        )

        # Верхняя панель
        top_lines = [
            f"[bold cyan]Пилот:[/bold cyan] {self.state.player}",
            f"[bold cyan]Система:[/bold cyan] {self.state.coordinates.get('system', 'nexus')}",
            f"[bold cyan]Звезда:[/bold cyan] {self.state.coordinates.get('star', 'nexus_alpha')}",
            f"[bold cyan]Координаты:[/bold cyan] "
            f"X:{self.state.coordinates.get('x', 0):.1f} "
            f"Y:{self.state.coordinates.get('y', 0):.1f} "
            f"Z:{self.state.coordinates.get('z', 0):.1f}",
            "",
            "[bold cyan]Команды:[/bold cyan] systems, stars, scan, jump, warp, move, fire",
            "", ""
        ][:8]
        layout["top"].update(Panel("\n".join(top_lines), title="СТАТУС КОРАБЛЯ"))

        # Средняя панель (логи)
        log_lines = list(reversed(self.state.logs))[:14][::-1]
        cooldown_anim = self.get_cooldown_animation()
        if cooldown_anim:
            log_lines.append(cooldown_anim)
        else:
            log_lines.append("")

        while len(log_lines) < 11:
            log_lines.append("")

        layout["middle"].update(Panel("\n".join(log_lines), title="ЛОГИ СОБЫТИЙ"))

        # Нижняя панель
        from rich.layout import Layout as RowLayout
        bottom_row = RowLayout()
        bottom_row.split_row(
            self._create_hull_panel(),
            self._create_weapons_panel()
        )
        layout["bottom"].update(bottom_row)

        # Панель ввода
        prompt = "> " if self.authenticated else "🔐 "
        display = prompt + self.current_input
        layout["input"].update(Panel(display, title="ВВОД КОМАНДЫ (Enter для отправки)", style="bright_blue"))

        return layout

    def _create_hull_panel(self):
        """Создание панели состояния корпуса"""
        lines = self._draw_hull().split('\n')
        while len(lines) < 4:
            lines.append("")
        return Panel("\n".join(lines), title="КОРПУС")

    def _draw_hull(self):
        """Отрисовка состояния корпуса"""
        def color(v):
            return "green" if v >= 70 else "yellow" if v >= 30 else "red"

        return f"""[{color(self.state.hull.get('bow', 0))}]Нос:     {self.state.hull.get('bow', 0)}%[/]
[{color(self.state.hull.get('port', 0))}]Левый:   {self.state.hull.get('port', 0)}%[/]
[{color(self.state.hull.get('starboard', 0))}]Правый:  {self.state.hull.get('starboard', 0)}%[/]
[{color(self.state.hull.get('stern', 0))}]Корма:   {self.state.hull.get('stern', 0)}%[/]"""

    def _create_weapons_panel(self):
        """Создание панели вооружения и инвентаря"""
        right_lines = self._draw_weapons_and_inventory().split('\n')
        if len(right_lines) > 7:
            right_lines = right_lines[:7]
        while len(right_lines) < 7:
            right_lines.append("")
        return Panel("\n".join(right_lines), title="ВООРУЖЕНИЕ И ИНВЕНТАРЬ")

    def _draw_weapons_and_inventory(self):
        """Отрисовка вооружения и инвентаря"""
        if not self.state.weapons and not self.state.inventory:
            return "Нет данных"

        lines = []
        lines.append("[bold]Оружие:[/bold]")

        # Отрисовка оружия с кулдаунами
        for weapon in ["laser", "missile", "railgun"]:
            if weapon in self.state.weapons:
                status = self.state.weapons[weapon]
                col = "green" if status >= 70 else "yellow" if status >= 30 else "red"

                # Проверяем кулдаун
                cd_bar = self.get_weapon_cooldown_bar(weapon)
                if cd_bar:
                    lines.append(f"  {weapon}: [{col}]{status}%[/] {cd_bar}")
                else:
                    lines.append(f"  {weapon}: [{col}]{status}%[/] [green]✓[/]")

        lines.append("")
        lines.append("[bold]Инвентарь:[/bold]")
        for k, v in self.state.inventory.items():
            lines.append(f"  {k}: {v}")

        if self.state.stats:
            lines.append("")
            lines.append("[bold]Статистика:[/bold]")
            lines.append(f"  🎯 Побед: {self.state.stats.get('enemies_defeated', 0)}")
            lines.append(f"  📋 Миссий: {self.state.stats.get('missions_completed', 0)}")

        return "\n".join(lines)