#!/usr/bin/env python3
"""
Wi-Fi Analyzer  —  matplotlib チャンネルグラフ版
ベル曲線でWi-Fiチャンネルの信号強度をビジュアライズ
操作: [1] 2.4GHz  [2] 5GHz  [3] 両方  [R] 再スキャン  [Q] 終了
"""

import sys, subprocess, importlib

# ── 依存パッケージの自動インストール ─────────────────────────────────────────
def _ensure(pkg, import_name=None):
    name = import_name or pkg
    try:
        importlib.import_module(name)
    except ImportError:
        print(f"[setup] {pkg} をインストール中...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            stdout=subprocess.DEVNULL,
        )
        print(f"[setup] {pkg} のインストール完了")

_ensure("matplotlib")
_ensure("numpy")

# ── GUI バックエンド自動選択 ──────────────────────────────────────────────────
import matplotlib

def _select_backend():
    candidates = [
        ("TkAgg",  "matplotlib.backends.backend_tkagg"),
        ("Qt5Agg", "matplotlib.backends.backend_qt5agg"),
        ("QtAgg",  "matplotlib.backends.backend_qtagg"),
        ("WXAgg",  "matplotlib.backends.backend_wxagg"),
        ("Agg",    "matplotlib.backends.backend_agg"),
    ]
    for name, module in candidates:
        try:
            importlib.import_module(module)
            matplotlib.use(name)
            print(f"[backend] {name} を使用")
            return name
        except Exception:
            continue
    print("[setup] PyQt5 をインストールします...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "PyQt5", "--quiet"],
        stdout=subprocess.DEVNULL,
    )
    print("[setup] PyQt5 のインストール完了")
    matplotlib.use("Qt5Agg")
    return "Qt5Agg"

_select_backend()

# ── 日本語フォント自動検出 ────────────────────────────────────────────────────
import matplotlib.font_manager as fm

def _setup_japanese_font():
    import platform, os, glob
    candidates = []
    system = platform.system()
    if system == "Windows":
        win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for pat in ["meiryo.ttc", "meiryob.ttc", "YuGothR.ttc", "YuGothM.ttc",
                    "msgothic.ttc", "msmincho.ttc"]:
            path = os.path.join(win_fonts, pat)
            if os.path.exists(path):
                candidates.append(path)
    elif system == "Darwin":
        for pat in ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                    "/Library/Fonts/Arial Unicode.ttf"]:
            if os.path.exists(pat):
                candidates.append(pat)
    else:
        candidates += glob.glob("/usr/share/fonts/**/NotoSansCJK*.ttc", recursive=True)
        candidates += glob.glob("/usr/share/fonts/**/NotoSansCJK*.otf", recursive=True)
    for path in candidates:
        try:
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            matplotlib.rcParams["font.family"] = prop.get_name()
            return
        except Exception:
            continue

_setup_japanese_font()

# ── 通常の import ─────────────────────────────────────────────────────────────
import random
from datetime import datetime
from dataclasses import dataclass, field

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.widgets import RadioButtons
from matplotlib.animation import FuncAnimation
import numpy as np

# ── カラーパレット ────────────────────────────────────────────────────────────
COLORS = [
    "#00FF41", "#FF4444", "#4499FF", "#FFEE00", "#FF44FF",
    "#00EEFF", "#FF8800", "#BB44FF", "#FF4488", "#88FF44",
]

# ── データモデル ──────────────────────────────────────────────────────────────
@dataclass
class Network:
    ssid: str
    bssid: str
    signal: int
    channel: int
    band: str
    security: str
    vendor: str
    connected: bool = False
    color: str = "#00FF41"
    _hist: list = field(default_factory=list)

    def __post_init__(self):
        self._hist = [self.signal]

    def fluctuate(self):
        self.signal = max(-95, min(-20, self.signal + random.randint(-3, 3)))
        self._hist.append(self.signal)
        if len(self._hist) > 60:
            self._hist.pop(0)

    @property
    def freq_mhz(self) -> int:
        if self.band == "2.4GHz":
            return 2412 + (self.channel - 1) * 5
        # IEEE 802.11 標準: 5000 + ch * 5 (全帯域共通)
        return 5000 + self.channel * 5

    @property
    def bandwidth_mhz(self) -> int:
        return 40 if self.band == "5GHz" else 20


# 5GHz 全チャンネル定義 (IEEE 802.11)
CH5_BANDS = {
    "UNII-1":  [36, 40, 44, 48],
    "UNII-2A": [52, 56, 60, 64],
    "UNII-2C": [100,104,108,112,116,120,124,128,132,136,140,144],
    "UNII-3":  [149,153,157,161,165],
    "UNII-4":  [169,173,177],
}
ALL_5G_CHANNELS = [ch for chs in CH5_BANDS.values() for ch in chs]


def make_networks():
    return [
        # ── 2.4 GHz ──
        Network("MyHome_2.4G",    "AA:BB:10", -42,  6, "2.4GHz", "WPA3", "ASUS",    color=COLORS[0], connected=True),
        Network("Neighbor-WiFi",  "AA:BB:11", -58,  6, "2.4GHz", "WPA2", "NEC",     color=COLORS[1]),
        Network("BUFFALO-G-5678", "AA:BB:12", -65, 11, "2.4GHz", "WPA2", "Buffalo", color=COLORS[2]),
        Network("FreeWiFi",       "AA:BB:13", -72,  1, "2.4GHz", "Open", "TP-Link", color=COLORS[3]),
        Network("IoT-Network",    "AA:BB:14", -77,  1, "2.4GHz", "WPA2", "Elecom",  color=COLORS[4]),
        Network("Office-Guest",   "AA:BB:15", -80, 11, "2.4GHz", "WPA2", "Cisco",   color=COLORS[5]),
        # ── 5 GHz: UNII-1 (ch36-48) ──
        Network("MyHome_5G",         "AA:BB:01", -38, 36, "5GHz", "WPA3", "ASUS",    color=COLORS[0], connected=True),
        Network("ntcm1-8b32f1-a",    "AA:BB:02", -62, 40, "5GHz", "WPA2", "NTT",     color=COLORS[1]),
        Network("coa-grp-net-4f",    "AA:BB:03", -65, 40, "5GHz", "WPA2", "Cisco",   color=COLORS[7]),
        Network("cweb-network",       "AA:BB:04", -68, 44, "5GHz", "WPA2", "TP-Link", color=COLORS[2]),
        Network("Office-5G",          "AA:BB:05", -74, 48, "5GHz", "WPA2", "Cisco",   color=COLORS[9]),
        # ── 5 GHz: UNII-2A (ch52-64) ──
        Network("coa-mc-net-2f",     "AA:BB:06", -78, 52, "5GHz", "WPA2", "Cisco",   color=COLORS[3]),
        Network("coa-grp-net-2f",    "AA:BB:07", -82, 56, "5GHz", "WPA2", "Cisco",   color=COLORS[8]),
        Network("Neighbor-5G-A",     "AA:BB:08", -71, 60, "5GHz", "WPA2", "NEC",     color=COLORS[5]),
        Network("Guest-5G",           "AA:BB:09", -85, 64, "5GHz", "WPA2", "Netgear", color=COLORS[6]),
        # ── 5 GHz: UNII-2C (ch100-144) ──
        Network("Enterprise-A",      "AA:BB:0A", -66,100, "5GHz", "WPA2-E","Cisco",  color=COLORS[1]),
        Network("Enterprise-B",      "AA:BB:0B", -70,108, "5GHz", "WPA2-E","Cisco",  color=COLORS[4]),
        Network("Hotel-WiFi",         "AA:BB:0C", -75,116, "5GHz", "WPA2", "Ruckus",  color=COLORS[2]),
        Network("Stadium-Net",        "AA:BB:0D", -80,124, "5GHz", "WPA2", "Aruba",   color=COLORS[7]),
        Network("Campus-5G",          "AA:BB:0E", -73,132, "5GHz", "WPA2-E","Meraki", color=COLORS[8]),
        Network("Hotspot-2C",         "AA:BB:0F", -88,140, "5GHz", "WPA2", "TP-Link", color=COLORS[3]),
        # ── 5 GHz: UNII-3 (ch149-165) ──
        Network("coa-mc-net-4f",     "AA:BB:10", -63,149, "5GHz", "WPA2", "Cisco",   color=COLORS[1]),
        Network("cweb-network",       "AA:BB:11", -70,153, "5GHz", "WPA2", "TP-Link", color=COLORS[3]),
        Network("coa-grp-net-4f-2",  "AA:BB:12", -72,157, "5GHz", "WPA2", "Cisco",   color=COLORS[4]),
        Network("Neighbor-5G-B",     "AA:BB:13", -79,161, "5GHz", "WPA2", "NEC",     color=COLORS[5]),
        Network("IoT-5G",             "AA:BB:14", -84,165, "5GHz", "WPA2", "Elecom",  color=COLORS[9]),
        # ── 5 GHz: UNII-4 (ch169-177) ──
        Network("NextGen-WiFi",       "AA:BB:15", -68,169, "5GHz", "WPA3", "Qualcomm",color=COLORS[6]),
        Network("6E-Bridge",          "AA:BB:16", -77,173, "5GHz", "WPA3", "Intel",   color=COLORS[8]),
    ]


def bell_curve(cx, sig, bw, x):
    sigma = bw / 2.5
    return -100.0 + (sig + 100.0) * np.exp(-0.5 * ((x - cx) / sigma) ** 2)


# ── グラフ描画ヘルパー ────────────────────────────────────────────────────────
def draw_band_axes(ax_ov, ax_main, nets, band_label,
                   BG, PANEL, GRID, TICK, LABEL):
    """1つの帯域分 (ミニマップ + メイン) を描画する共通関数"""
    is_5g = all(n.band == "5GHz" for n in nets)

    # ── ミニマップ ──────────────────────────────────────────────────────
    ax_ov.set_facecolor(PANEL)
    freqs = [n.freq_mhz for n in nets]
    fmin, fmax = min(freqs) - 80, max(freqs) + 80
    ax_ov.set_xlim(fmin, fmax); ax_ov.set_ylim(-100, -18)
    for sp in ax_ov.spines.values(): sp.set_color("#333333")
    ax_ov.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for f in [fmin, (fmin + fmax) / 2, fmax]:
        ax_ov.text(f, -19.2, f"{int(f)} MHz",
                   color="#888888", fontsize=7, ha="center", va="top")
    ax_ov.plot([fmin, fmax, fmax, fmin, fmin],
               [-20, -20, -99, -99, -20], color="#555555", lw=0.7, alpha=0.5)
    x2 = np.linspace(fmin, fmax, 2000)
    for n in nets:
        y = bell_curve(n.freq_mhz, n.signal, 25, x2)
        ax_ov.plot(x2, y, color=n.color, lw=0.8, alpha=0.85)
        ax_ov.fill_between(x2, y, -100, color=n.color, alpha=0.12)

    # ── メイングラフ ────────────────────────────────────────────────────
    ax_main.set_facecolor(PANEL)
    ax_main.set_xlim(fmin, fmax); ax_main.set_ylim(-100, -20)
    for dbm in range(-90, -20, 10):
        ax_main.axhline(dbm, color=GRID, lw=0.6, zorder=0)
    ax_main.set_yticks(range(-90, -20, 10))
    ax_main.set_yticklabels([str(v) for v in range(-90, -20, 10)],
                            color=TICK, fontsize=9)
    ax_main.set_ylabel("シグナル強度 [dBm]", color=LABEL, fontsize=9, labelpad=6)

    ch_ticks, ch_labels = [], []
    if is_5g:
        for ch in ALL_5G_CHANNELS:
            f = 5000 + ch * 5
            if fmin <= f <= fmax:
                ch_ticks.append(f); ch_labels.append(str(ch))
    else:
        for ch in range(1, 14):
            f = 2412 + (ch - 1) * 5
            if fmin <= f <= fmax:
                ch_ticks.append(f); ch_labels.append(str(ch))
    ax_main.set_xticks(ch_ticks)
    ax_main.set_xticklabels(ch_labels, color=LABEL, fontsize=8,
                             rotation=45, ha="right")
    ax_main.set_xlabel("Wifi チャンネル", color=LABEL, fontsize=9, labelpad=4)
    for sp in ax_main.spines.values(): sp.set_color("#333333")
    ax_main.tick_params(axis="both", length=0)

    x = np.linspace(fmin, fmax, 4000)
    used: dict = {}
    for n in sorted(nets, key=lambda n: n.signal):
        y = bell_curve(n.freq_mhz, n.signal, n.bandwidth_mhz, x)
        ax_main.fill_between(x, y, -100, color=n.color,
                             alpha=0.22 if n.connected else 0.16, zorder=2)
        ax_main.plot(x, y, color=n.color,
                     lw=2.2 if n.connected else 1.6, alpha=0.95, zorder=3)
        lx, ly = n.freq_mhz, n.signal + 2.0
        key = (round(lx / 15), round(ly / 4))
        while used.get(key):
            ly -= 5; key = (round(lx / 15), round(ly / 4))
        used[key] = True
        ax_main.text(lx, ly, f"{n.ssid}{' ✓' if n.connected else ''}",
                     color=n.color, fontsize=8.5, ha="center", va="bottom",
                     fontweight="bold" if n.connected else "normal", zorder=4)

    # UNII サブバンド区切り線 (5GHz のみ)
    if is_5g:
        unii_boundaries = [5250, 5470, 5725, 5850]  # 各UNII帯の境界MHz
        unii_labels     = ["UNII-1","UNII-2A","UNII-2C","UNII-3","UNII-4"]
        prev_f = fmin
        for i, boundary in enumerate(unii_boundaries + [fmax]):
            mid = (prev_f + min(boundary, fmax)) / 2
            if fmin < mid < fmax:
                ax_main.text(mid, -21.5, unii_labels[i],
                             color="#555555", fontsize=7.5,
                             ha="center", va="top", style="italic")
            if fmin < boundary < fmax:
                ax_main.axvline(boundary, color="#444444", lw=0.8,
                                linestyle="--", zorder=1)
            prev_f = boundary

    ax_main.set_title(
        f"Wifi Analyzer   {band_label}   {len(nets)} ネットワーク"
        f"   {datetime.now().strftime('%H:%M:%S')}",
        color="#CCCCCC", fontsize=10, pad=6, loc="left",
    )

    seen: set = set(); handles = []
    for n in sorted(nets, key=lambda n: n.signal, reverse=True):
        uid = n.ssid + n.bssid
        if uid not in seen:
            seen.add(uid)
            handles.append(mpatches.Patch(color=n.color,
                                          label=f"{n.ssid}   {n.signal} dBm"))
    ax_main.legend(handles=handles,
                   bbox_to_anchor=(1.0, 0.93),
                   loc="upper right",
                   borderaxespad=0,
                   fontsize=7.5,
                   facecolor="#222222", edgecolor="#444444",
                   labelcolor="white", framealpha=0.88, ncol=3)


# ── メインアプリ ──────────────────────────────────────────────────────────────
class WifiAnalyzer:
    BG    = "#111111"
    PANEL = "#1A1A1A"
    GRID  = "#2A2A2A"
    TICK  = "#666666"
    LABEL = "#AAAAAA"

    BAND_LABELS = ["2.4 GHz", "5 GHz", "両方"]
    BAND_KEYS   = ["2.4GHz",  "5GHz",  "両方"]

    def __init__(self):
        self.all_nets   = make_networks()
        self.band_index = 1   # デフォルト: 5GHz
        self._tick      = 0

        plt.style.use("dark_background")
        self.fig = plt.figure(figsize=(15, 9), facecolor=self.BG)
        try:
            self.fig.canvas.manager.set_window_title("Wi-Fi Analyzer")
        except Exception:
            pass

        self._build_layout()
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        self.ani = FuncAnimation(
            self.fig, self._update, interval=1000, cache_frame_data=False
        )

    # ── レイアウト構築 ────────────────────────────────────────────────────────
    def _build_layout(self):
        """バンドモードに応じて axes を動的に再構成する"""
        self.fig.clear()
        key = self.BAND_KEYS[self.band_index]

        # 外側: 左(ラジオ) + 右(グラフエリア)
        outer = gridspec.GridSpec(
            1, 2, figure=self.fig,
            width_ratios=[1, 13],
            left=0.01, right=0.99, top=0.97, bottom=0.06,
            wspace=0.02,
        )

        # ── 左: RadioButtons ──────────────────────────────────────────
        self.ax_radio = self.fig.add_subplot(outer[0, 0])
        self.ax_radio.set_facecolor(self.PANEL)
        for sp in self.ax_radio.spines.values():
            sp.set_color("#333333")
        self.ax_radio.tick_params(
            left=False, bottom=False, labelleft=False, labelbottom=False)
        self.ax_radio.text(0.5, 0.97, "バンド", transform=self.ax_radio.transAxes,
                           ha="center", va="top", color=self.LABEL, fontsize=9)

        self.radio = RadioButtons(
            self.ax_radio,
            labels=self.BAND_LABELS,
            active=self.band_index,
            activecolor="#00EEFF",
        )
        for lbl in self.radio.labels:
            lbl.set_color(self.LABEL); lbl.set_fontsize(9)
        self.radio.on_clicked(self._on_band_click)

        # ── 右: グラフエリア ──────────────────────────────────────────
        right = outer[0, 1]

        if key == "両方":
            # 2段 × 2列: 上行=ミニマップ×2、下行=メイン×2
            inner = gridspec.GridSpecFromSubplotSpec(
                2, 2,
                subplot_spec=right,
                height_ratios=[1, 5],
                hspace=0.06, wspace=0.06,
            )
            self.ax_ov24   = self.fig.add_subplot(inner[0, 0])
            self.ax_ov5    = self.fig.add_subplot(inner[0, 1])
            self.ax_main24 = self.fig.add_subplot(inner[1, 0])
            self.ax_main5  = self.fig.add_subplot(inner[1, 1])
        else:
            # 2段 × 1列
            inner = gridspec.GridSpecFromSubplotSpec(
                2, 1,
                subplot_spec=right,
                height_ratios=[1, 5],
                hspace=0.04,
            )
            self.ax_ov   = self.fig.add_subplot(inner[0, 0])
            self.ax_main = self.fig.add_subplot(inner[1, 0])

    # ── フィルタ ──────────────────────────────────────────────────────────────
    def _nets(self, band=None):
        b = band or self.BAND_KEYS[self.band_index]
        if b == "両方":
            return self.all_nets
        return [n for n in self.all_nets if n.band == b]

    # ── アニメーション更新 ────────────────────────────────────────────────────
    def _update(self, frame):
        self._tick += 1
        if self._tick % 5 == 0:
            for n in self.all_nets:
                n.fluctuate()
        self._redraw()

    def _redraw(self):
        key = self.BAND_KEYS[self.band_index]
        if key == "両方":
            for ax in [self.ax_ov24, self.ax_ov5, self.ax_main24, self.ax_main5]:
                ax.cla()
            nets24 = self._nets("2.4GHz")
            nets5  = self._nets("5GHz")
            draw_band_axes(self.ax_ov24, self.ax_main24, nets24, "2.4 GHz",
                           self.BG, self.PANEL, self.GRID, self.TICK, self.LABEL)
            draw_band_axes(self.ax_ov5,  self.ax_main5,  nets5,  "5 GHz",
                           self.BG, self.PANEL, self.GRID, self.TICK, self.LABEL)
        else:
            self.ax_ov.cla(); self.ax_main.cla()
            draw_band_axes(self.ax_ov, self.ax_main, self._nets(),
                           self.BAND_LABELS[self.band_index],
                           self.BG, self.PANEL, self.GRID, self.TICK, self.LABEL)

    # ── バンド切り替え ────────────────────────────────────────────────────────
    def _on_band_click(self, label):
        self.band_index = self.BAND_LABELS.index(label)
        self._build_layout()
        self._redraw()
        self.fig.canvas.draw_idle()

    # ── キー操作 ─────────────────────────────────────────────────────────────
    def _on_key(self, event):
        if event.key in ("q", "escape", "ctrl+c"):
            plt.close("all")
        elif event.key == "r":
            for n in self.all_nets:
                n.fluctuate()
            self._redraw()
            self.fig.canvas.draw_idle()
        elif event.key in ("1", "2", "3"):
            idx = int(event.key) - 1
            self.band_index = idx
            self._build_layout()
            self._redraw()
            self.radio.set_active(idx)
            self.fig.canvas.draw_idle()

    def run(self):
        plt.show()


# ── エントリポイント ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Wi-Fi Analyzer を起動中...")
    print("  バンド切替: [1] 2.4GHz  [2] 5GHz  [3] 両方")
    print("  [R] 再スキャン   [Q] 終了")
    WifiAnalyzer().run()
