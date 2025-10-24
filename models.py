"""
Modelos de datos para el scraper de empresas SAÓ FCT
"""
from dataclasses import dataclass, asdict
from typing import Optional
import json
from datetime import datetime


@dataclass
class EmpresaCompleta:
    """Modelo de datos para una empresa completa con todos los campos"""
    id_empresa: str
    cif: str = ""
    nombre: str = ""
    direccion: str = ""
    provincia: str = ""
    localidad: str = ""
    cp: str = ""
    telefono: str = ""
    fax: str = ""
    actividad: str = ""
    nombre_gerente: str = ""
    nif_gerente: str = ""
    email: str = ""
    tipo: str = ""

    def to_dict(self) -> dict:
        """Convierte el objeto a diccionario para serialización JSON"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'EmpresaCompleta':
        """Crea un objeto desde un diccionario"""
        return cls(**data)


@dataclass
class ScrapingResult:
    """Resultado del scraping con metadata"""
    empresas: list[EmpresaCompleta]
    timestamp: str
    total_empresas: int
    errores: int = 0
    tiempo_total: Optional[str] = None

    def to_json(self, filepath: str) -> None:
        """Exporta el resultado a un archivo JSON"""
        data = {
            "metadata": {
                "timestamp": self.timestamp,
                "total_empresas": self.total_empresas,
                "errores": self.errores,
                "tiempo_total": self.tiempo_total
            },
            "empresas": [empresa.to_dict() for empresa in self.empresas]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> 'ScrapingResult':
        """Carga un resultado desde un archivo JSON"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        empresas = [EmpresaCompleta.from_dict(emp) for emp in data['empresas']]
        metadata = data['metadata']
        
        return cls(
            empresas=empresas,
            timestamp=metadata['timestamp'],
            total_empresas=metadata['total_empresas'],
            errores=metadata.get('errores', 0),
            tiempo_total=metadata.get('tiempo_total')
        )

