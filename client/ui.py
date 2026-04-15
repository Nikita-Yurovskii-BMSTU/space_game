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
        self.shake_frames = 0  # счётчик кадров тряски
        self.shake_intensity = 0  # сила тряски

        # Кулдауны оружия
        self.weapon_cooldowns = {}  # {weapon: {"active": True, "remaining": 5, "start_time": timestamp}}

    def shake(self, intensity=3, duration=5):
        """Запустить тряску экрана"""
        self.shake_frames = duration
        self.shake_intensity = intensity

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
            Layout(name="top", size=5),
            Layout(name="middle", size=16),
            Layout(name="bottom", size=10),
            Layout(name="input", size=3)
        )

        # Верхняя панель
        top_lines = [
            f"[bold cyan]Пилот:[/bold cyan] {self.state.player} | Система: {self.state.coordinates.get('system', 'nexus')} | Звезда: {self.state.coordinates.get('star', 'nexus_alpha')}",
            f"[bold cyan]Координаты:[/bold cyan] X:{self.state.coordinates.get('x', 0):.1f} Y:{self.state.coordinates.get('y', 0):.1f} Z:{self.state.coordinates.get('z', 0):.1f}",
            f"[bold cyan]Цель:[/bold cyan] {self.state.target or 'нет'}",
            "",
            "[bold cyan]Команды:[/bold cyan] scan, target, fire, move, warp, jump, auto"
        ][:5]
        layout["top"].update(Panel("\n".join(top_lines), title="СТАТУС КОРАБЛЯ", height=5))

        # Средняя панель (логи)
        all_logs = list(self.state.logs)
        visible_lines = 14

        if len(all_logs) > visible_lines:
            log_lines = all_logs[:visible_lines]
        else:
            log_lines = all_logs[:]
            while len(log_lines) < visible_lines:
                log_lines.append("")

        cooldown_anim = self.get_cooldown_animation()
        if cooldown_anim:
            if log_lines:
                log_lines[0] = cooldown_anim

        layout["middle"].update(Panel("\n".join(log_lines), title="ЛОГИ СОБЫТИЙ", height=visible_lines))

        # Нижняя панель — 3 колонки
        from rich.layout import Layout as RowLayout
        bottom_row = RowLayout()
        bottom_row.split_row(
            self._create_hull_panel(),
            self._create_overview_panel(),
            self._create_weapons_panel()
        )
        layout["bottom"].update(bottom_row)

        # Панель ввода
        prompt = "> " if self.authenticated else "🔐 "
        display = prompt + self.current_input
        layout["input"].update(Panel(display, title="ВВОД КОМАНДЫ", style="bright_blue", height=3))

        return layout

    def _create_overview_panel(self):
        """Создание панели обзора"""
        lines = self._draw_overview().split('\n')
        if len(lines) > 8:
            lines = lines[:8]
        while len(lines) < 8:
            lines.append("")
        return Panel("\n".join(lines), title="ОБЗОР")

    def _draw_overview(self):
        """Отрисовка обзора"""
        if not hasattr(self.state, 'overview') or not self.state.overview:
            return "[dim]Нет данных. Используйте scan[/dim]"

        lines = []
        for i, obj in enumerate(self.state.overview[:8]):
            # Определяем иконку
            icon = self._get_object_icon(obj)

            # Формируем строку
            if obj['type'] == 'enemy':
                hp_percent = (obj.get('hp', 0) / obj.get('max_hp', 1)) * 100
                hp_color = "green" if hp_percent > 70 else "yellow" if hp_percent > 30 else "red"
                line = f"{i + 1}. {icon} {obj['name']} [{hp_color}]{hp_percent:.0f}%[/] ({obj['distance']:.0f}m)"
            elif obj['type'] == 'player':
                line = f"{i + 1}. {icon} {obj['name']} ({obj['distance']:.0f}m)"
            else:
                line = f"{i + 1}. {icon} {obj['name']} ({obj['distance']:.0f}m)"

            # Подсветка цели
            if self.state.target and obj['name'] == self.state.target:
                line = f"[bold yellow]> {line}[/bold yellow]"
            else:
                line = f"  {line}"

            lines.append(line)

        return "\n".join(lines)

    def _get_object_icon(self, obj):
        """Получить иконку для объекта"""
        icons = {
            'station': '🛸',
            'planet': '🪐',
            'belt': '☄️',
            'debris_field': '💀',
            'ice_field': '❄️',
            'enemy': {'safe': '🟢', 'moderate': '🟡', 'dangerous': '🟠', 'deadly': '🔴'}.get(obj.get('danger', 'moderate'),
                                                                                         '👾'),
            'player': '👤',
            'npc': '🤖'
        }

        if obj['type'] == 'enemy':
            return icons['enemy']
        return icons.get(obj['type'], '•')

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
        lines = []
        lines.append("[bold]Установленное оружие:[/bold]")

        # Показываем только установленное оружие
        installed = self.state.ship.get('installed_weapons', [])
        if installed:
            for weapon in installed:
                # Получаем статус оружия из state.weapons
                status = self.state.weapons.get(weapon, 100)
                col = "green" if status >= 70 else "yellow" if status >= 30 else "red"

                cd_bar = self.get_weapon_cooldown_bar(weapon)
                if cd_bar:
                    lines.append(f"  {weapon}: [{col}]{status}%[/] {cd_bar}")
                else:
                    lines.append(f"  {weapon}: [{col}]{status}%[/] [green]✓[/]")
        else:
            lines.append("  [dim]нет оружия[/dim]")

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