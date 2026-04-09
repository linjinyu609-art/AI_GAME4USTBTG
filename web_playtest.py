import html
import io
import secrets
from contextlib import redirect_stdout
from http import cookies
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from campus_game.engine import GameEngine

SESSIONS: dict[str, GameEngine] = {}


def get_engine(environ):
    cookie = cookies.SimpleCookie(environ.get("HTTP_COOKIE", ""))
    sid = cookie.get("sid").value if cookie.get("sid") else None
    new_sid = None
    if not sid or sid not in SESSIONS:
        sid = secrets.token_hex(16)
        SESSIONS[sid] = GameEngine()
        new_sid = sid
    return sid, SESSIONS[sid], new_sid


def run_action(engine: GameEngine, action: str) -> str:
    mapping = {
        "pull": engine.pull_once,
        "battle": engine.battle,
        "trial": engine.abyss_trial,
        "expedition": engine.mystery_expedition,
        "daily": engine.daily_center,
        "save": engine.save,
        "reset": engine.reset_daily,
    }
    fn = mapping.get(action)
    if not fn:
        return ""
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    return buf.getvalue()


def status_html(engine: GameEngine) -> str:
    state = engine.state
    team = engine._get_team()
    team_power = sum(h.power for h in team)
    buffs = "<br>".join(
        [f"{b['name']} (+{int(b['value']*100)}%) 剩余{b['duration']}战" for b in state.active_buffs]
    ) or "无"

    return f"""
    <h2>校园异能扭蛋 - Web Playtest</h2>
    <p><b>玩家</b>: {html.escape(state.name)} | <b>等级</b>: {state.account_level} | <b>章节</b>: {state.chapter}-{state.stage}</p>
    <p><b>钻石</b>: {state.gems} | <b>金币</b>: {state.coins} | <b>体力</b>: {state.stamina} | <b>试炼票</b>: {state.trial_tickets} | <b>碎片</b>: {state.relic_shards}</p>
    <p><b>队伍基础战力</b>: {team_power}</p>
    <p><b>每日任务</b>: 抽卡{state.daily['pull']}/5 推图{state.daily['battle']}/4 事件{state.daily['event']}/2 试炼{state.daily['trial']}/1 已领奖:{state.daily['claim']}</p>
    <p><b>当前增益</b>:<br>{buffs}</p>
    """


def app(environ, start_response):
    sid, engine, new_sid = get_engine(environ)
    message = ""

    if environ.get("REQUEST_METHOD") == "POST":
        try:
            size = int(environ.get("CONTENT_LENGTH", "0"))
        except ValueError:
            size = 0
        body = environ["wsgi.input"].read(size).decode("utf-8") if size > 0 else ""
        form = parse_qs(body)
        action = form.get("action", [""])[0]
        message = run_action(engine, action)

    content = f"""
    <html>
    <head>
      <meta charset='utf-8'/>
      <title>校园异能扭蛋 Web 测试</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; background: #111; color: #eaeaea; }}
        button {{ margin: 4px; padding: 10px 14px; border-radius: 8px; border: 1px solid #444; background: #222; color: #fff; cursor: pointer; }}
        button:hover {{ background: #333; }}
        pre {{ background: #1c1c1c; padding: 12px; border-radius: 8px; border: 1px solid #333; white-space: pre-wrap; }}
        .card {{ background: #161616; border: 1px solid #2e2e2e; border-radius: 10px; padding: 14px; margin-bottom: 16px; }}
      </style>
    </head>
    <body>
      <div class='card'>
        {status_html(engine)}
      </div>
      <form method='POST'>
        <button name='action' value='pull'>单抽</button>
        <button name='action' value='battle'>推图</button>
        <button name='action' value='trial'>深渊试炼</button>
        <button name='action' value='expedition'>秘境远征</button>
        <button name='action' value='daily'>每日任务</button>
        <button name='action' value='save'>保存</button>
        <button name='action' value='reset'>重置每日(测试)</button>
      </form>
      <h3>最近日志</h3>
      <pre>{html.escape(message) if message else '点击上方按钮开始测试。'}</pre>
      <p>会话ID: {sid}</p>
    </body>
    </html>
    """.encode("utf-8")

    headers = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(content)))]
    if new_sid:
        headers.append(("Set-Cookie", f"sid={new_sid}; Path=/; HttpOnly"))
    start_response("200 OK", headers)
    return [content]


if __name__ == "__main__":
    port = 8000
    print(f"Web playtest 启动: http://127.0.0.1:{port}")
    with make_server("0.0.0.0", port, app) as httpd:
        httpd.serve_forever()
