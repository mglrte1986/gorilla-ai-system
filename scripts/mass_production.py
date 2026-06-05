#!/usr/bin/env python3
"""
HECTOR - Orquestador de Producción en Masa
Coordina renderizado de video, sincronización con Google Sheets y distribución
Autorización: Agente 8686
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Importar motores
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.video_engine import HectorVideoEngine

try:
    from src.google_sheets_connector import HectorGoogleSheetsConnector
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - HECTOR ORCHESTRATOR - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HectorProductionOrchestrator:
    """
    Orquestador principal de HECTOR
    Coordina todos los componentes del sistema de producción en masa
    """
    
    def __init__(self, asset_name: str, batch_size: int = 100):
        """
        Inicializa el orquestador
        
        Args:
            asset_name (str): Nombre del activo a producir
            batch_size (int): Número de secuencias a procesar
        """
        self.asset_name = asset_name
        self.batch_size = batch_size
        self.video_engine = HectorVideoEngine(asset_name)
        
        self.sheets_available = False
        if SHEETS_AVAILABLE:
            try:
                self.sheets_connector = HectorGoogleSheetsConnector()
                self.sheets_available = True
            except Exception as e:
                logger.warning(f"⚠️  Google Sheets no disponible: {e}")
        
        self.production_log = {
            'asset_name': asset_name,
            'started_at': datetime.now().isoformat(),
            'batch_size': batch_size,
            'results': []
        }
        
        logger.info(f"🦍 HECTOR Orchestrator inicializado para: {asset_name}")
    
    def generate_sequence_ids(self) -> List[str]:
        """Genera IDs de secuencia para el batch"""
        sequence_ids = [f"V{str(i+1).zfill(4)}" for i in range(self.batch_size)]
        logger.info(f"📋 Generadas {len(sequence_ids)} secuencias")
        return sequence_ids
    
    def render_batch(self) -> List[Dict]:
        """Renderiza el batch completo"""
        logger.info(f"🎬 Iniciando renderizado de batch: {self.batch_size} videos")
        
        sequence_ids = self.generate_sequence_ids()
        results = self.video_engine.render_batch(sequence_ids)
        
        # Procesar resultados
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        
        logger.info(f"✅ Exitosos: {successful} | ❌ Fallidos: {failed}")
        
        self.production_log['render_results'] = {
            'total': len(results),
            'successful': successful,
            'failed': failed,
            'timestamp': datetime.now().isoformat()
        }
        
        return results
    
    def sync_to_sheets(self):
        """Sincroniza resultados con Google Sheets"""
        if not self.sheets_available:
            logger.warning("⚠️  Google Sheets no disponible - saltando sincronización")
            return
        
        try:
            logger.info("📊 Sincronizando resultados con Google Sheets...")
            
            log_data = {
                'status': 'COMPLETADO',
                'asset_count': self.batch_size,
                'kpi_value': self.production_log['render_results']['successful'],
                'error': '',
                'agent_id': 'HECTOR'
            }
            
            self.sheets_connector.write_production_log('Registro de inversiones de Google Finance', log_data)
            logger.info("✅ Datos sincronizados con Google Sheets")
            
        except Exception as e:
            logger.error(f"❌ Error sincronizando sheets: {e}")
    
    def generate_report(self) -> Dict:
        """Genera reporte final de producción"""
        logger.info("📋 Generando reporte de producción...")
        
        self.production_log['completed_at'] = datetime.now().isoformat()
        self.production_log['status'] = 'COMPLETADO'
        
        # Guardar reporte
        report_file = Path('reports') / f"production_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(self.production_log, f, indent=2)
        
        logger.info(f"✅ Reporte guardado: {report_file}")
        
        return self.production_log
    
    def execute_production_cycle(self):
        """Ejecuta ciclo completo de producción"""
        logger.info("🦍 HECTOR - INICIANDO CICLO DE PRODUCCIÓN EN MASA")
        logger.info("=" * 70)
        
        try:
            # Fase 1: Renderizado de batch
            logger.info("\n📍 FASE 1: RENDERIZADO DE VIDEO")
            self.render_batch()
            
            # Fase 2: Sincronización con Google Sheets
            logger.info("\n📍 FASE 2: SINCRONIZACIÓN CON GOOGLE SHEETS")
            self.sync_to_sheets()
            
            # Fase 3: Generación de reporte
            logger.info("\n📍 FASE 3: GENERACIÓN DE REPORTE")
            report = self.generate_report()
            
            # Resumen
            logger.info("\n" + "=" * 70)
            logger.info("✅ CICLO DE PRODUCCIÓN COMPLETADO")
            logger.info(f"📊 Videos generados: {report['render_results']['successful']}")
            logger.info(f"❌ Videos fallidos: {report['render_results']['failed']}")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ ERROR EN CICLO DE PRODUCCIÓN: {e}")
            self.production_log['error'] = str(e)
            self.production_log['status'] = 'FALLIDO'
            self.generate_report()
            return False

def main():
    parser = argparse.ArgumentParser(
        description='HECTOR - Orquestador de Producción en Masa',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 scripts/mass_production.py --batch-size 100
  python3 scripts/mass_production.py --asset "PRODUCCION_COMUNIDAD_01" --batch-size 50
  python3 scripts/mass_production.py --verbose
        """
    )
    
    parser.add_argument(
        '--asset',
        default='PRODUCCION_COMUNIDAD_01',
        help='Nombre del activo a producir (default: PRODUCCION_COMUNIDAD_01)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Número de secuencias a procesar (default: 100)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Modo verbose (más información de logging)'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Crear y ejecutar orquestador
        orchestrator = HectorProductionOrchestrator(
            asset_name=args.asset,
            batch_size=args.batch_size
        )
        
        success = orchestrator.execute_production_cycle()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Producción interrumpida por usuario")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ FALLO CRÍTICO: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
