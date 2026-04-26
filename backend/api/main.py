from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys
import json
import time
import math

def sanitize_data(data: Any) -> Any:
    """Recursively replace non-JSON-compliant float values (inf, nan) with None."""
    if isinstance(data, float):
        if math.isinf(data) or math.isnan(data):
            return None
        return data
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    return data

# DB Imports
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ─── Setup Native Paths ───────────────────────────────────────────────────────
API_DIR = Path(__file__).resolve().parent
ENGINE_BUILD_DIR = API_DIR.parent / "engine" / "build"

def _configure_native_paths() -> None:
    for path in (API_DIR, ENGINE_BUILD_DIR):
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.append(path_str)
        if sys.platform == "win32" and sys.version_info >= (3, 8) and path.exists():
            os.add_dll_directory(path_str)

_configure_native_paths()

try:
    import logistics_engine
except ImportError as exc:
    raise RuntimeError(f"Failed to load logistics_engine.") from exc

# ─── Database Configuration (SQLite) ──────────────────────────────────────────
DATABASE_URL = "sqlite:///./logistics.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SavedConfig(Base):
    __tablename__ = "configs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    data = Column(Text)

Base.metadata.create_all(bind=engine)

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Logistics Optimiser API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Models ─────────────────────────────────────────────────────────

class NodeModel(BaseModel):
    id: int
    name: str
    type: str
    lat: float
    lon: float
    demand: float = 0.0

class EdgeModel(BaseModel):
    id: int
    from_node: int
    to_node: int
    distance_km: float
    time_min: float

class VehicleModel(BaseModel):
    id: int
    name: str
    depot_id: int
    capacity: float
    max_range_km: float

class SolverRequest(BaseModel):
    nodes: List[NodeModel]
    edges: List[EdgeModel]
    depots: List[int]
    customers: List[int]
    warehouses: List[int]
    vehicles: List[VehicleModel]
    return_to_depot: bool = True
    w_distance: float = 1.0
    w_time: float = 0.5
    w_cost: float = 0.3

class ConfigSaveRequest(BaseModel):
    name: str
    nodes: List[NodeModel]
    vehicles: List[VehicleModel]

# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "engine": "logistics_engine linked"}

@app.post("/solve")
def solve_vrp(req: SolverRequest):
    return _solve_internal(req, logistics_engine.RoutingStrategy.GREEDY_2OPT)

@app.post("/compare")
def compare_vrp(req: SolverRequest):
    res_greedy = _solve_internal(req, logistics_engine.RoutingStrategy.GREEDY_ONLY)
    res_opt = _solve_internal(req, logistics_engine.RoutingStrategy.GREEDY_2OPT)
    return [res_greedy, res_opt]

def _solve_internal(req: SolverRequest, strategy: logistics_engine.RoutingStrategy):
    start_time = time.time()
    try:
        # 1. Build the C++ Graph
        graph = logistics_engine.Graph()
        id_map = {}
        type_map = {
            "DEPOT": logistics_engine.NodeType.DEPOT,
            "CUSTOMER": logistics_engine.NodeType.CUSTOMER,
            "WAREHOUSE": logistics_engine.NodeType.WAREHOUSE
        }

        for n in req.nodes:
            node = logistics_engine.Node(n.id, n.name, type_map.get(n.type, logistics_engine.NodeType.CUSTOMER), n.lat, n.lon, n.demand)
            id_map[n.id] = graph.add_node(node)

        for e in req.edges:
            if e.from_node in id_map and e.to_node in id_map:
                edge = logistics_engine.Edge(e.id, id_map[e.from_node], id_map[e.to_node], e.distance_km, e.time_min, 1.0, False)
                graph.add_edge(edge)

        # 2. Setup Problem
        prob = logistics_engine.VRPProblem()
        prob.depots = [id_map[d] for d in req.depots if d in id_map]
        prob.customers = [id_map[c] for c in req.customers if c in id_map]
        prob.return_to_depot = req.return_to_depot
        
        backend_vehicles = []
        for v in req.vehicles:
            if v.depot_id in id_map:
                backend_vehicles.append(logistics_engine.Vehicle(v.id, v.name, id_map[v.depot_id], v.capacity, v.max_range_km))
        prob.vehicles = backend_vehicles

        # 3. Solve
        cfg = logistics_engine.SolverConfig()
        cfg.strategy = strategy
        cfg.verbose = True
        solver = logistics_engine.VRPSolver(graph, cfg)
        solution = solver.solve(prob)
        
        reverse_id_map = {v: k for k, v in id_map.items()}
        elapsed = (time.time() - start_time) * 1000
        
        result = {
            "total_distance_km": solution.total_distance_km,
            "total_time_min": solution.total_time_min,
            "execution_time_ms": elapsed,
            "routes": [{
                "vehicle_id": r.vehicle_id, 
                "stops": [reverse_id_map.get(s, s) for s in r.stops], 
                "total_distance_km": r.total_distance_km, 
                "load": r.load,
                "feasible": r.feasible
            } for r in solution.routes],
            "algorithm_used": solution.algorithm_used,
            "is_complete": solution.is_complete()
        }
        return sanitize_data(result)
    except Exception as e:
        print(f"[ERROR] Solver failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── DB Endpoints ────────────────────────────────────────────────────────────

@app.post("/save-config")
def save_config(req: ConfigSaveRequest):
    db = SessionLocal()
    try:
        config_data = {"nodes": [n.dict() for n in req.nodes], "vehicles": [v.dict() for v in req.vehicles]}
        # Sanitize to prevent JSON encoding errors if inf/nan exist
        sanitized_data = sanitize_data(config_data)
        
        db_config = db.query(SavedConfig).filter(SavedConfig.name == req.name).first()
        if db_config:
            db_config.data = json.dumps(sanitized_data)
        else:
            db_config = SavedConfig(name=req.name, data=json.dumps(sanitized_data))
            db.add(db_config)
        db.commit()
        return {"message": f"Config '{req.name}' saved successfully"}
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Save config failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/load-config/{name}")
def load_config(name: str):
    db = SessionLocal()
    try:
        db_config = db.query(SavedConfig).filter(SavedConfig.name == name).first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")
        return json.loads(db_config.data)
    finally:
        db.close()

@app.get("/list-configs")
def list_configs():
    db = SessionLocal()
    try:
        configs = db.query(SavedConfig).all()
        return [c.name for c in configs]
    finally:
        db.close()
