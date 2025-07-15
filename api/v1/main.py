from datetime import datetime
import logging
import os

from fastapi import FastAPI, HTTPException, BackgroundTasks
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from typing import List
import httpx

from api.v1.models import ViaIpeInstitution

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://viaipe_user:viaipe_pass@postgres:5432/viaipe_monitoring")
VIAIPE_API_URL = os.getenv("VIAIPE_API_URL", "https://viaipe.rnp.br/api/norte")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="ViaIpe Data Collector API", version="1.0.0")


def determine_region_state(lat: float, lng: float) -> tuple:
    """Determina região e estado baseado nas coordenadas"""
    if lat > 0:
        return "Norte", "RR" if lng < -60 else "AP"
    elif lat > -5:
        if lng > -50:
            return "Norte", "PA"
        elif lng > -55:
            return "Norte", "AM"
        else:
            return "Norte", "AC"
    elif lat > -15:
        return "Nordeste", "TO" if lng < -45 else "MA"
    else:
        return "Centro-Oeste", "MT" if lng < -55 else "MG"


async def fetch_viaipe_data() -> List[ViaIpeInstitution]:
    """Coleta dados da API do ViaIpe"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(VIAIPE_API_URL)
            response.raise_for_status()

            data = response.json()
            institutions = []

            for item in data:
                try:
                    institution = ViaIpeInstitution(**item)
                    institutions.append(institution)
                except Exception as e:
                    logger.warning(f"Erro ao processar instituição {item.get('id', 'desconhecida')}: {e}")
                    continue

            logger.info(f"Coletados dados de {len(institutions)} instituições")
            return institutions

    except Exception as e:
        logger.error(f"Erro ao coletar dados do ViaIpe: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na coleta de dados: {str(e)}")


def store_institution_data_safe(institution: ViaIpeInstitution) -> bool:
    """Armazena dados de uma instituição com transação individual"""
    try:
        with SessionLocal() as db:
            try:
                lat = float(institution.lat)
                lng = float(institution.lng)
                region, state = determine_region_state(lat, lng)

                institution_query = text("""
                    INSERT INTO institutions (id, name, latitude, longitude, region, state)
                    VALUES (:id, :name, :lat, :lng, :region, :state)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        region = EXCLUDED.region,
                        state = EXCLUDED.state
                """)

                db.execute(institution_query, {
                    'id': institution.id,
                    'name': institution.name,
                    'lat': lat,
                    'lng': lng,
                    'region': region,
                    'state': state
                })

                if institution.data.interfaces:
                    interface = institution.data.interfaces[0]

                    availability = 100.0
                    if institution.data.smoke:
                        availability = max(0, 100 - institution.data.smoke.loss)

                    in_util = 0.0
                    out_util = 0.0
                    if interface.max_traffic_down > 0 and interface.traffic_in:
                        in_util = min(100, (interface.traffic_in / interface.max_traffic_down) * 100)
                    if interface.max_traffic_up > 0 and interface.traffic_out:
                        out_util = min(100, (interface.traffic_out / interface.max_traffic_up) * 100)

                    metrics_query = text("""
                        INSERT INTO traffic_metrics (
                            time, institution_id, traffic_in, traffic_out,
                            latency_ms, packet_loss_percent, availability_percent,
                            bandwidth_utilization_in_percent, bandwidth_utilization_out_percent
                        ) VALUES (
                            NOW(), :inst_id, :traffic_in, :traffic_out,
                            :latency, :loss, :availability, :in_util, :out_util
                        )
                    """)

                    smoke = institution.data.smoke
                    db.execute(metrics_query, {
                        'inst_id': institution.id,
                        'traffic_in': interface.traffic_in or 0,
                        'traffic_out': interface.traffic_out or 0,
                        'latency': smoke.val if smoke else None,
                        'loss': smoke.loss if smoke else 0,
                        'availability': availability,
                        'in_util': in_util,
                        'out_util': out_util
                    })

                db.commit()
                return True

            except SQLAlchemyError as e:
                db.rollback()
                logger.error(f"Erro SQL ao processar {institution.id}: {e}")
                return False
            except Exception as e:
                db.rollback()
                logger.error(f"Erro geral ao processar {institution.id}: {e}")
                return False

    except Exception as e:
        logger.error(f"Erro ao conectar ao banco para {institution.id}: {e}")
        return False


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now()}


@app.post("/collect-data")
async def collect_data_endpoint(background_tasks: BackgroundTasks):
    """Endpoint para coletar dados do ViaIpe manualmente"""
    background_tasks.add_task(collect_and_store_data)
    return {"message": "Coleta de dados iniciada", "timestamp": datetime.now()}


@app.get("/institutions")
async def get_institutions():
    """Lista todas as instituições"""
    try:
        with SessionLocal() as db:
            query = text("""
                SELECT id, name, latitude, longitude, region, state
                FROM institutions
                ORDER BY name
            """)

            result = db.execute(query)
            institutions = []

            for row in result:
                institutions.append({
                    "id": row[0],
                    "name": row[1],
                    "latitude": float(row[2]),
                    "longitude": float(row[3]),
                    "region": row[4],
                    "state": row[5]
                })

            return {"institutions": institutions, "total": len(institutions)}
    except Exception as e:
        logger.error(f"Erro ao buscar instituições: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/availability-stats")
async def get_availability_stats(hours: int = 24):
    """Obtém estatísticas de disponibilidade"""
    try:
        with SessionLocal() as db:
            query = text("""
                SELECT 
                    tm.institution_id,
                    AVG(tm.availability_percent) as avg_availability,
                    AVG(tm.traffic_in / 1000000) as avg_bandwidth_in_mbps,
                    AVG(tm.traffic_out / 1000000) as avg_bandwidth_out_mbps,
                    MAX(tm.time) as last_update,
                    COUNT(*) as data_points
                FROM traffic_metrics tm
                WHERE tm.time >= NOW() - INTERVAL '%s hours'
                GROUP BY tm.institution_id
                ORDER BY avg_availability DESC
            """ % hours)

            result = db.execute(query)
            stats = []

            for row in result:
                stats.append({
                    "institution_id": row[0],
                    "availability_percent": round(float(row[1] or 0), 2),
                    "avg_bandwidth_in_mbps": round(float(row[2] or 0), 2),
                    "avg_bandwidth_out_mbps": round(float(row[3] or 0), 2),
                    "last_update": row[4],
                    "data_points": row[5]
                })

            return {"stats": stats, "total": len(stats)}
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/counts")
async def debug_counts():
    """Endpoint de debug para verificar contagens"""
    try:
        with SessionLocal() as db:
            inst_count = db.execute(text("SELECT COUNT(*) FROM institutions")).scalar()
            metrics_count = db.execute(text("SELECT COUNT(*) FROM traffic_metrics")).scalar()
            latest_metric = db.execute(text("SELECT MAX(time) FROM traffic_metrics")).scalar()

            return {
                "institutions_count": inst_count,
                "metrics_count": metrics_count,
                "latest_metric_time": latest_metric
            }
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    """Endpoint raiz"""
    return {"message": "ViaIpe API funcionando!", "version": "1.0.0"}


async def collect_and_store_data():
    """Função principal de coleta e armazenamento com transações individuais"""
    try:
        logger.info("Iniciando coleta de dados do ViaIpe")
        institutions = await fetch_viaipe_data()

        success_count = 0
        total_count = len(institutions)

        for i, institution in enumerate(institutions, 1):
            logger.info(f"Processando {i}/{total_count}: {institution.id}")

            if store_institution_data_safe(institution):
                success_count += 1

            if i % 50 == 0:
                logger.info(f"Progresso: {i}/{total_count} processadas, {success_count} sucessos")

        logger.info(f"Coleta finalizada: {success_count}/{total_count} instituições armazenadas com sucesso")

        with SessionLocal() as db:
            inst_count = db.execute(text("SELECT COUNT(*) FROM institutions")).scalar()
            metrics_count = db.execute(text("SELECT COUNT(*) FROM traffic_metrics")).scalar()
            logger.info(f"Verificação final: {inst_count} instituições, {metrics_count} métricas no banco")

    except Exception as e:
        logger.error(f"Erro na coleta de dados: {e}")


@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação"""
    logger.info("API ViaIpe iniciada")
