from bottle import route, run, request, static_file
import cassie_play

@route('/')
def index():
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>C.A.S.S.I.E. 工具集</title>
    <style>
        @property --angle {
            syntax: '<angle>';
            initial-value: 0deg;
            inherits: false;
        }

        @property --angle2 {
            syntax: '<angle>';
            initial-value: 180deg;
            inherits: false;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background-color: #0a0c10;
            background-image: radial-gradient(circle at 25% 40%, rgba(40, 48, 60, 0.5) 0%, rgba(20, 25, 35, 0.9) 40%, #0a0c10 100%);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            width: 820px;
            max-width: 100%;
        }

        .header {
            margin-bottom: 28px;
            opacity: 0;
            animation: headerFadeIn 0.6s ease 0.1s forwards;
        }

        @keyframes headerFadeIn {
            0% { opacity: 0; transform: translateY(-8px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .header h1 {
            font-size: 28px;
            font-weight: 500;
            color: #eef2f5;
            letter-spacing: 0.3px;
            margin-bottom: 4px;
        }

        .header .subtitle {
            font-size: 13px;
            color: #8e9aaf;
            font-weight: 400;
            letter-spacing: 0.2px;
        }

        .menu-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
        }

        .menu-card {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            background: rgba(22, 27, 34, 0.35);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 20px 18px 18px 18px;
            text-decoration: none;
            color: #eef2f5;
            transition: transform 0.3s cubic-bezier(0.2, 0, 0, 1), box-shadow 0.35s cubic-bezier(0.2, 0, 0, 1), background 0.3s ease, border-color 0.3s ease;
            position: relative;
            min-height: 130px;
            box-shadow: 4px 6px 12px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
            overflow: hidden;
            cursor: pointer;
            opacity: 0;
            animation: cardFadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .menu-card:nth-child(1) { animation-delay: 0.1s; }
        .menu-card:nth-child(2) { animation-delay: 0.18s; }
        .menu-card:nth-child(3) { animation-delay: 0.26s; }
        .menu-card:nth-child(4) { animation-delay: 0.34s; }
        .menu-card:nth-child(5) { animation-delay: 0.42s; }
        .menu-card:nth-child(6) { animation-delay: 0.50s; }

        @keyframes cardFadeIn {
            0% { opacity: 0; transform: translateY(20px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .menu-card::before {
            content: '';
            position: absolute;
            top: var(--mouse-y, 50%);
            left: var(--mouse-x, 50%);
            width: 200px;
            height: 200px;
            background: radial-gradient(circle, rgba(255, 255, 255, 0.04) 0%, transparent 60%);
            border-radius: 50%;
            transform: translate(-50%, -50%);
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.4s ease;
        }

        .menu-card:hover::before {
            opacity: 1;
        }

        .menu-card .border-glow {
            position: absolute;
            inset: -2px;
            border-radius: 17px;
            padding: 2px;
            background: conic-gradient(from var(--angle, 0deg), transparent, rgba(108, 126, 160, 0.15), transparent, rgba(108, 126, 160, 0.15), transparent);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
            animation: borderSpin 4s linear infinite;
            opacity: 0;
            transition: opacity 0.4s ease;
        }

        .menu-card:hover .border-glow {
            opacity: 1;
        }

        .menu-card .border-glow2 {
            position: absolute;
            inset: -2px;
            border-radius: 17px;
            padding: 2px;
            background: conic-gradient(from var(--angle2, 180deg), transparent, rgba(140, 160, 200, 0.1), transparent, rgba(140, 160, 200, 0.1), transparent);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
            animation: borderSpin2 4.8s linear infinite;
            opacity: 0;
            transition: opacity 0.4s ease;
        }

        .menu-card:hover .border-glow2 {
            opacity: 1;
        }

        @keyframes borderSpin {
            0% { --angle: 0deg; }
            100% { --angle: 360deg; }
        }

        @keyframes borderSpin2 {
            0% { --angle2: 180deg; }
            100% { --angle2: 540deg; }
        }

        .menu-card:hover {
            background: rgba(30, 36, 48, 0.55);
            border-color: rgba(255, 255, 255, 0.12);
            transform: translateY(-8px);
            box-shadow: 8px 14px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }

        .menu-card:active {
            transform: scale(0.97);
            transition-duration: 0.05s;
        }

        .menu-card .icon {
            font-size: 18px;
            font-weight: 500;
            color: #cbd5e6;
            margin-bottom: 10px;
            padding: 4px 12px;
            background: rgba(30, 36, 48, 0.3);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.04);
            transition: transform 0.3s cubic-bezier(0.2, 0, 0, 1), background 0.3s ease, border-color 0.3s ease;
            position: relative;
            z-index: 1;
            backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
        }

        .menu-card:hover .icon {
            background: rgba(37, 43, 56, 0.4);
            border-color: rgba(255, 255, 255, 0.08);
            transform: scale(1.04) rotate(2deg);
        }

        .menu-card .title {
            font-size: 15px;
            font-weight: 500;
            color: #eef2f5;
            margin-bottom: 4px;
            transition: color 0.3s ease, transform 0.3s cubic-bezier(0.2, 0, 0, 1);
            position: relative;
            z-index: 1;
        }

        .menu-card:hover .title {
            color: #ffffff;
            transform: translateX(4px);
        }

        .menu-card .desc {
            font-size: 12px;
            color: #8e9aaf;
            line-height: 1.4;
            transition: color 0.4s ease;
            position: relative;
            z-index: 1;
        }

        .menu-card:hover .desc {
            color: #a8b4c8;
        }

        .menu-card .arrow {
            position: absolute;
            bottom: 16px;
            right: 16px;
            font-size: 14px;
            color: #4a5260;
            opacity: 0.5;
            transition: transform 0.3s cubic-bezier(0.2, 0, 0, 1), color 0.3s ease, opacity 0.3s ease;
            z-index: 2;
        }

        .menu-card:hover .arrow {
            transform: translateX(8px);
            color: #7c8aa0;
            opacity: 1;
        }

        .menu-card .bg-breath {
            position: absolute;
            inset: 0;
            border-radius: 16px;
            background: radial-gradient(ellipse at 30% 20%, rgba(60, 100, 200, 0.03), transparent 70%);
            pointer-events: none;
            opacity: 0.4;
            animation: breath 4s ease-in-out infinite alternate;
            z-index: 0;
        }

        @keyframes breath {
            0% { opacity: 0.2; transform: scale(1); }
            100% { opacity: 0.6; transform: scale(1.05); }
        }

        @media (max-width: 600px) {
            .menu-grid {
                grid-template-columns: 1fr;
            }
            .menu-card {
                min-height: 100px;
            }
            .menu-card::before {
                width: 120px;
                height: 120px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>C.A.S.S.I.E.</h1>
            <div class="subtitle">工具集</div>
        </div>
        <div class="menu-grid">
            <a href="/cassie_play" target="_blank" class="menu-card">
                <div class="bg-breath"></div>
                <div class="border-glow"></div>
                <div class="border-glow2"></div>
                <span class="icon">广播</span>
                <span class="title">广播生成器</span>
                <span class="desc">C.A.S.S.I.E. 语音广播合成</span>
                <span class="arrow">→</span>
            </a>
        </div>
    </div>
    <script>
        document.querySelectorAll('.menu-card').forEach(function(card) {
            card.addEventListener('mousemove', function(e) {
                var rect = card.getBoundingClientRect();
                var x = ((e.clientX - rect.left) / rect.width) * 100;
                var y = ((e.clientY - rect.top) / rect.height) * 100;
                card.style.setProperty('--mouse-x', x + '%');
                card.style.setProperty('--mouse-y', y + '%');
                var angle = Math.atan2(e.clientY - rect.top - rect.height/2, e.clientX - rect.left - rect.width/2) * 180 / Math.PI;
                card.style.setProperty('--angle', angle + 'deg');
                card.style.setProperty('--angle2', (angle + 180) + 'deg');
            });
        });
    </script>
</body>
</html>
    '''

@route('/static/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root='static')

if __name__ == '__main__':
    run(host='localhost', port=8080, debug=True)