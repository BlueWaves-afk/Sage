import { useEffect, useRef } from "react";

// Rotating wireframe globe rendered on canvas — the landing hero centrepiece.
// Pure math (lat/lon graticule projected to 2D), no textures or WebGL needed.
export default function Globe({ size = 620 }: { size?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current!;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);

    const R = size * 0.42;
    const cx = size / 2;
    const cy = size / 2;
    let rot = 0;
    let raf = 0;

    const project = (lat: number, lon: number) => {
      const la = (lat * Math.PI) / 180;
      const lo = (lon * Math.PI) / 180 + rot;
      const x = Math.cos(la) * Math.sin(lo);
      const y = Math.sin(la);
      const z = Math.cos(la) * Math.cos(lo);
      return { x: cx + x * R, y: cy - y * R, z };
    };

    const draw = () => {
      ctx.clearRect(0, 0, size, size);

      // Soft inner glow
      const grad = ctx.createRadialGradient(cx + R * 0.25, cy - R * 0.2, R * 0.1, cx, cy, R);
      grad.addColorStop(0, "rgba(56,198,238,0.35)");
      grad.addColorStop(0.6, "rgba(30,90,150,0.20)");
      grad.addColorStop(1, "rgba(8,20,40,0.05)");
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // Meridians
      for (let lon = 0; lon < 180; lon += 15) {
        ctx.beginPath();
        let started = false;
        for (let lat = -90; lat <= 90; lat += 4) {
          const p = project(lat, lon);
          if (p.z < 0) {
            started = false;
            continue;
          }
          ctx.globalAlpha = 0.15 + p.z * 0.35;
          if (!started) {
            ctx.moveTo(p.x, p.y);
            started = true;
          } else ctx.lineTo(p.x, p.y);
        }
        ctx.strokeStyle = "#4db8e0";
        ctx.lineWidth = 0.7;
        ctx.stroke();
      }

      // Parallels
      for (let lat = -75; lat <= 75; lat += 15) {
        ctx.beginPath();
        let started = false;
        for (let lon = 0; lon <= 360; lon += 4) {
          const p = project(lat, lon);
          if (p.z < 0) {
            started = false;
            continue;
          }
          ctx.globalAlpha = 0.12 + p.z * 0.3;
          if (!started) {
            ctx.moveTo(p.x, p.y);
            started = true;
          } else ctx.lineTo(p.x, p.y);
        }
        ctx.strokeStyle = "#3a8fc0";
        ctx.lineWidth = 0.7;
        ctx.stroke();
      }

      ctx.globalAlpha = 1;
      // Rim
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(90,200,240,0.5)";
      ctx.lineWidth = 1.2;
      ctx.stroke();

      rot += 0.0016;
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [size]);

  return <canvas ref={ref} style={{ width: size, height: size, maxWidth: "100%" }} />;
}
