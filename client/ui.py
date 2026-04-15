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

        self.cooldown_active = False
        self.cooldown_remaining = 0
        self.cooldown_start_time = 0
        self.animation_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.animation_index = 0
        self.weapon_cooldowns = {}

    def shake(self, intensity=3, duration=5):
        pass

    def set_cooldown(self, remaining, message=""):
        self.cooldown_active = True
        self.cooldown_remaining = remaining
        self.cooldown_start_time = time.time()
        if message:
            self.state.add_log(f"[yellow]{message}[/yellow]")

    def set_weapon_cooldown(self, weapon, remaining, message=""):
        self.weapon_cooldowns[weapon] = {
            "active": True,
            "remaining": remaining,
            "start_time": time.time()
        }
        if message:
            self.state.add_log(f"[yellow]{message}[/yellow]")

    def get_cooldown_animation(self):
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
        progress = int((total - remaining) / total * 15)
        bar = "█" * progress + "░" * (15 - progress)

        return f"{spinner} [yellow]{bar} {remaining:.1f}с[/yellow]"

    def get_weapon_cooldown_bar(self, weapon):
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
        progress = int((total - remaining) / total * 6)
        bar = "█" * progress + "░" * (6 - progress)

        return f"{bar}{remaining:.0f}s"

    def draw_layout(self):
        layout = Layout()

        # Горизонтальное разделение
        layout.split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )

        # Правая часть: обзор сверху, вооружение снизу
        layout["right"].split_column(
            Layout(name="overview", ratio=2),
            Layout(name="weapons", ratio=1)
        )

        # Левая часть: статус сверху, логи снизу
        layout["left"].split_column(
            Layout(name="status", size=12),
            Layout(name="logs", ratio=1),
            Layout(name="input", size=3)
        )

        # Статус корабля
        layout["status"].update(Panel(self._draw_status(), title="[bold cyan]СТАТУС[/bold cyan]", border_style="cyan"))

        # Логи
        layout["logs"].update(Panel(self._draw_logs(), title="[bold cyan]ЛОГИ[/bold cyan]", border_style="blue"))

        # Строка ввода
        cooldown_anim = self.get_cooldown_animation()
        prompt = f"{cooldown_anim} > " if cooldown_anim else ("> " if self.authenticated else "🔐 ")
        layout["input"].update(Panel(prompt + self.current_input, title="[bold cyan]ВВОД[/bold cyan]", style="bright_blue", border_style="blue"))

        # Обзор
        layout["overview"].update(Panel(self._draw_overview(), title="[bold cyan]ОБЗОР[/bold cyan]", border_style="green"))

        # Вооружение и инвентарь
        layout["weapons"].update(Panel(self._draw_weapons(), title="[bold cyan]ВООРУЖЕНИЕ / ИНВЕНТАРЬ[/bold cyan]", border_style="yellow"))

        return layout

    def _draw_status(self):
        lines = []
        lines.append(f"[cyan]Пилот:[/cyan] {self.state.player}")
        lines.append(f"[cyan]Система:[/cyan] {self.state.coordinates.get('system', 'nexus')}")
        lines.append(f"[cyan]Звезда:[/cyan] {self.state.coordinates.get('star', 'nexus_alpha')[:14]}")
        c = self.state.coordinates
        lines.append(f"[cyan]Коорд:[/cyan] {c.get('x', 0):.0f} {c.get('y', 0):.0f} {c.get('z', 0):.0f}")
        lines.append(f"[yellow]🎯 {self.state.target}[/yellow]" if self.state.target else "[dim]🎯 нет цели[/dim]")
        lines.append("")
        lines.append("[cyan]КОРПУС[/cyan]")

        hull = self.state.hull
        for part, label in [('bow', 'нос'), ('port', 'лев'), ('starboard', 'пр'), ('stern', 'корм')]:
            val = hull.get(part, 0)
            color = "green" if val >= 70 else "yellow" if val >= 30 else "red"
            bar = "█" * (val // 5) + "░" * (20 - val // 5)
            lines.append(f"  {label}: [{color}]{bar}[/] {val}%")

        return "\n".join(lines)

    def _draw_logs(self):
        logs = list(self.state.logs)
        visible = 12
        if len(logs) > visible:
            log_lines = logs[:visible]
        else:
            log_lines = logs[:]
            while len(log_lines) < visible:
                log_lines.append("")
        return "\n".join(log_lines)

    def _draw_overview(self):
        if not hasattr(self.state, 'overview') or not self.state.overview:
            return "[dim]Нет данных. Используйте scan[/dim]"

        lines = []
        sorted_obj = sorted(self.state.overview, key=lambda x: x['distance'])

        lines.append(f'[dim]{"#":<2} {"Название":<14} {"Дист":<6} Статус[/dim]')
        lines.append("[dim]" + "-" * 34 + "[/dim]")

        for i, obj in enumerate(sorted_obj[:10]):
            icon = self._get_icon(obj)
            name = obj['name'][:14].ljust(14)
            dist = self._fmt_dist(obj['distance'])

            if obj['type'] == 'enemy':
                if 'hp' in obj and obj.get('max_hp'):
                    hp_pct = int(obj['hp'] / obj['max_hp'] * 100)
                    hp_bar = "█" * (hp_pct // 10) + "░" * (10 - hp_pct // 10)
                    hp_color = "green" if hp_pct > 70 else "yellow" if hp_pct > 30 else "red"
                    status = f"[{hp_color}]{hp_bar}[/]"
                else:
                    status = "[red]БОЙ[/]"
            else:
                status = self._get_danger(obj)

            if self.state.target and obj['name'] == self.state.target:
                lines.append(f"[yellow]→{i+1:<2} {icon} {name} {dist:<6} {status}[/yellow]")
            else:
                color = self._get_color(obj)
                lines.append(f"  {i+1:<2} {icon} [{color}]{name}[/] {dist:<6} {status}")

        lines.append("")
        lines.append("[dim]🛸 🪐 ☄️ 💀 👾 👤[/dim]")
        return "\n".join(lines)

    def _draw_weapons(self):
        lines = []

        # Оружие
        lines.append("[cyan]УСТАНОВЛЕНО[/cyan]")
        installed = self.state.ship.get('installed_weapons', [])
        if installed:
            for w in installed:
                status = self.state.weapons.get(w, 100)
                color = "green" if status >= 70 else "yellow" if status >= 30 else "red"
                cd = self.get_weapon_cooldown_bar(w)
                if cd:
                    lines.append(f"  {w[:8]}: [{color}]{status}%[/] [dim]{cd}[/dim]")
                else:
                    lines.append(f"  {w[:8]}: [{color}]{status}%[/] [green]✔[/green]")
        else:
            lines.append("  [dim]нет[/dim]")

        lines.append("")
        lines.append("[cyan]ИНВЕНТАРЬ[/cyan]")
        inv = self.state.inventory
        lines.append(f"  📦 ремки: {inv.get('repair_kits', 0)}")
        lines.append(f"  🚀 ракеты: {inv.get('missiles', 0)}")
        lines.append(f"  🔧 лом: {inv.get('scrap', 0)}")

        # Статистика
        stats = self.state.stats
        if stats:
            lines.append("")
            lines.append("[cyan]СТАТИСТИКА[/cyan]")
            lines.append(f"  🎯 побед: {stats.get('enemies_defeated', 0)}")

        return "\n".join(lines)

    def _get_icon(self, obj):
        icons = {'station': '🛸', 'planet': '🪐', 'belt': '☄️',
                 'debris_field': '💀', 'enemy': '👾', 'player': '👤', 'npc': '🤖'}
        return icons.get(obj.get('type'), '•')

    def _get_color(self, obj):
        colors = {'station': 'cyan', 'planet': 'green', 'belt': 'yellow',
                  'debris_field': 'red', 'enemy': 'red', 'player': 'magenta'}
        danger = obj.get('danger', 'safe')
        if danger == 'moderate':
            return 'yellow'
        elif danger == 'dangerous':
            return 'orange1'
        elif danger == 'deadly':
            return 'red'
        return colors.get(obj.get('type'), 'white')

    def _get_danger(self, obj):
        danger = obj.get('danger', 'safe')
        if danger == 'safe':
            return "[dim]safe[/]"
        elif danger == 'moderate':
            return "[yellow]![/]"
        elif danger == 'dangerous':
            return "[orange1]!![/]"
        elif danger == 'deadly':
            return "[red]!!![/]"
        return "[dim]-[/]"

    def _fmt_dist(self, dist):
        if dist < 1000:
            return f"{dist:.0f}m"
        elif dist < 1000000:
            return f"{dist/1000:.0f}km"
        else:
            return f"{dist/1000000:.1f}au"