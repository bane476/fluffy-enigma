import React, { useEffect, useRef } from 'react';
import { Node, VRPSolution } from '../types';

interface RouteMapProps {
  nodes: Node[];
  solution: VRPSolution | null;
}

export const RouteMap: React.FC<RouteMapProps> = ({ nodes, solution }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (nodes.length === 0) return;

    // 1. Find bounds for scaling
    const lats = nodes.map(n => n.lat);
    const lons = nodes.map(n => n.lon);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);

    const padding = 40;
    const width = canvas.width - padding * 2;
    const height = canvas.height - padding * 2;

    const scaleX = (lon: number) => padding + (maxLon === minLon ? width / 2 : (lon - minLon) / (maxLon - minLon) * width);
    const scaleY = (lat: number) => canvas.height - (padding + (maxLat === minLat ? height / 2 : (lat - minLat) / (maxLat - minLat) * height));

    // 2. Draw Edges (Routes)
    if (solution) {
      const colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
      solution.routes.forEach((route, idx) => {
        ctx.beginPath();
        ctx.strokeStyle = colors[idx % colors.length];
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        
        for (let i = 0; i < route.stops.length - 1; i++) {
          const from = nodes.find(n => n.id === route.stops[i]);
          const to = nodes.find(n => n.id === route.stops[i+1]);
          if (from && to) {
            ctx.moveTo(scaleX(from.lon), scaleY(from.lat));
            ctx.lineTo(scaleX(to.lon), scaleY(to.lat));
          }
        }
        ctx.stroke();
      });
    }

    // 3. Draw Nodes
    nodes.forEach(node => {
      const x = scaleX(node.lon);
      const y = scaleY(node.lat);

      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      
      if (node.type === 'DEPOT') ctx.fillStyle = '#1e40af';
      else if (node.type === 'WAREHOUSE') ctx.fillStyle = '#166534';
      else ctx.fillStyle = '#92400e';
      
      ctx.fill();
      ctx.strokeStyle = 'white';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#1e293b';
      ctx.font = '10px Inter';
      ctx.fillText(node.name, x + 8, y + 4);
    });

  }, [nodes, solution]);

  return (
    <div className="card" style={{ gridColumn: 'span 2', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <h2>🗺️ Network Topology & Optimized Paths</h2>
      <canvas 
        ref={canvasRef} 
        width={800} 
        height={400} 
        style={{ background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', width: '100%', maxWidth: '800px' }}
      />
      <div style={{ marginTop: '12px', display: 'flex', gap: '20px', fontSize: '0.8rem' }}>
        <span><span style={{ color: '#1e40af' }}>●</span> Depot</span>
        <span><span style={{ color: '#166534' }}>●</span> Warehouse</span>
        <span><span style={{ color: '#92400e' }}>●</span> Customer</span>
      </div>
    </div>
  );
};
