document.addEventListener('DOMContentLoaded', function () {
    function initAll() {
        document.querySelectorAll('.neuron-decoration').forEach(function(el) {
            if (el.querySelector('canvas')) return;
            var c = document.createElement('canvas');
            el.appendChild(c);
            run(c, el);
        });
    }
    function run(canvas, box) {
        var ctx = canvas.getContext('2d'), ps = [], N = 22, D = 130, w, h;
        function resize() {
            var r = box.getBoundingClientRect();
            w = canvas.width = r.width; h = canvas.height = r.height;
            ps = [];
            for (var i = 0; i < N; i++)
                ps.push({x:Math.random()*w, y:Math.random()*h, vx:(Math.random()-0.5)*0.3, vy:(Math.random()-0.5)*0.3, r:Math.random()*2.5+1.5, p:Math.random()*6.28});
        }
        function draw() {
            if (!box.isConnected) return;
            ctx.clearRect(0, 0, w, h);
            // Nodes: ORANGE (#E8843C), Connections: CELESTE (#4DA8DA)
            for (var i = 0; i < ps.length; i++) {
                var a = ps[i];
                a.x += a.vx; a.y += a.vy; a.p += 0.012;
                if(a.x<0)a.x=w; if(a.x>w)a.x=0; if(a.y<0)a.y=h; if(a.y>h)a.y=0;
                // Connections first (behind nodes)
                for (var j = i+1; j < ps.length; j++) {
                    var b = ps[j], dx = a.x-b.x, dy = a.y-b.y, d = Math.sqrt(dx*dx+dy*dy);
                    if (d < D) {
                        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y);
                        ctx.strokeStyle = 'rgba(77,168,218,' + ((1-d/D)*0.25) + ')';
                        ctx.lineWidth = 1.2; ctx.stroke();
                    }
                }
                // Node (orange)
                var al = 0.5 + 0.25 * Math.sin(a.p);
                ctx.beginPath(); ctx.arc(a.x, a.y, a.r, 0, 6.28);
                ctx.fillStyle = 'rgba(232,132,60,' + al + ')'; ctx.fill();
            }
            requestAnimationFrame(draw);
        }
        resize(); draw();
        new ResizeObserver(function(){resize()}).observe(box);
    }
    initAll();
    new MutationObserver(function(){ setTimeout(initAll, 300); }).observe(document.body, {childList:true, subtree:true});
});
