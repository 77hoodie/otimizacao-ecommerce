#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Otimização de Combustível para E-commerce com Integração de Mapas
Versão com OpenRoute Service para cálculo automático de rotas
"""

import sqlite3
import numpy as np
import uvicorn
import httpx
import asyncio
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configuração da API de mapas
OPENROUTE_BASE_URL = os.getenv("OPENROUTE_BASE_URL", "https://api.openrouteservice.org/v2")
OPENROUTE_API_KEY = os.getenv("OPENROUTE_API_KEY", "YOUR_API_KEY_HERE")

# Classe de otimização (copiada do sistema original)
class OtimizadorCombustivel:
    def __init__(self):
        # Coeficientes empíricos baseados em dados reais
        self.a1 = 0.08   # Consumo base (L/km)
        self.a2 = -0.001 # Eficiência por velocidade
        self.a3 = 0.00003 # Penalização quadrática
        self.a4 = 0.01   # Penalização por peso
        
        # Custo do tempo (R$ por hora)
        self.custo_hora_motorista = 25.0
        self.custo_hora_veiculo = 15.0
        self.custo_total_hora = self.custo_hora_motorista + self.custo_hora_veiculo
        
        # Perfis específicos por veículo
        self.perfis_veiculo = {
            "fiorino": {"fator_consumo": 0.95, "capacidade_tanque": 55, "nome": "Fiat Fiorino"},
            "expert": {"fator_consumo": 1.0, "capacidade_tanque": 65, "nome": "Peugeot Expert"}, 
            "transit": {"fator_consumo": 1.15, "capacidade_tanque": 80, "nome": "Ford Transit"}
        }
        
        # Fatores por tipo de rota
        self.fatores_rota = {
            "urbana": {"fator_consumo": 1.2, "fator_tempo_parada": 3.0, "velocidade_media_parada": 15},
            "interior": {"fator_consumo": 0.9, "fator_tempo_parada": 5.0, "velocidade_media_parada": 20}
        }

    def otimizar_velocidade(self, distancia_km: float, massa_kg: float, preco_combustivel: float,
                          consumo_base_kmh: float, custo_motorista_hora: float, tipo_rota: str = "urbana",
                          tipo_veiculo: str = "fiorino", paradas: int = 5, nivel_combustivel: float = 0.8):
        """Otimização simplificada compatível com API de mapas"""
        
        print(f"DEBUG - Otimizando para distância: {distancia_km} km")
        
        # Ajustar limites de velocidade baseado no modelo matemático
        # Faixas corrigidas conforme documentação no notebook de análise
        if distancia_km < 1.0:  # Distâncias muito curtas (< 1km)
            v_min, v_max = 15, 30  # Velocidades muito baixas
        elif distancia_km < 5.0:  # Distâncias curtas (1-5km)
            v_min, v_max = 20, 50  # Velocidades urbanas
        elif distancia_km < 15.0:  # Distâncias médias (5-15km)
            v_min, v_max = 30, 70  # Velocidades urbanas/arteriais
        elif distancia_km < 50.0:  # Distâncias longas (15-50km)
            v_min, v_max = 50, 90  # Velocidades rodoviárias
        else:  # Distâncias muito longas (>50km)
            v_min, v_max = 60, 110  # Velocidades rodoviárias altas
        
        print(f"DEBUG - Faixa de velocidades: {v_min}-{v_max} km/h")
        
        # Velocidades para análise
        velocidades = np.linspace(v_min, v_max, 50)
        custos = []
        dados_grafico = []
        
        for v in velocidades:
            # Tempo de viagem
            tempo_viagem = distancia_km / v
            
            # Custo combustível ajustado para cenário urbano
            # Em velocidades baixas urbanas, o consumo aumenta significativamente
            fator_urbano = 1.0
            if v < 30:
                fator_urbano = 1.4  # +40% de consumo em velocidades muito baixas
            elif v < 50:
                fator_urbano = 1.2  # +20% de consumo em velocidades baixas
            elif v > 70:
                fator_urbano = 1.3  # +30% de consumo em velocidades altas urbanas
                
            consumo_base = max(distancia_km / consumo_base_kmh, 0.05)  # Mínimo 0.05L
            consumo_ajustado = consumo_base * fator_urbano
            custo_combustivel = consumo_ajustado * preco_combustivel
            
            # Custo tempo (incluir tempo de parada em semáforos para velocidades baixas)
            tempo_paradas = 0
            if v < 40:
                # Adicionar tempo de paradas para velocidades urbanas baixas
                tempo_paradas = distancia_km * 0.02  # 0.02h por km em paradas
            
            tempo_total = tempo_viagem + tempo_paradas
            custo_tempo = tempo_total * custo_motorista_hora
            
            # Custo total
            custo_total = custo_combustivel + custo_tempo
            custos.append(custo_total)
            
            # Dados para gráfico
            dados_grafico.append({
                'velocidade': round(v, 1),
                'custo_total': round(custo_total, 2),
                'custo_combustivel': round(custo_combustivel, 2),
                'custo_tempo': round(custo_tempo, 2),
                'tempo_viagem': round(tempo_total, 3)
            })
        
        # Encontrar velocidade ótima
        idx_otimo = np.argmin(custos)
        velocidade_otima = velocidades[idx_otimo]
        custo_minimo = custos[idx_otimo]
        
        print(f"DEBUG - Velocidade ótima encontrada: {velocidade_otima} km/h")
        
        # Velocidade de referência (sempre 40 km/h para cenário urbano)
        v_ref = 40
        tempo_ref = distancia_km / v_ref
        
        # Aplicar mesmo fator urbano da referência
        fator_ref = 1.2  # Velocidade moderada urbana
        consumo_ref = max(distancia_km / consumo_base_kmh, 0.05) * fator_ref
        
        # Adicionar tempo de paradas para referência
        tempo_paradas_ref = distancia_km * 0.01  # Menos paradas em 40km/h
        tempo_total_ref = tempo_ref + tempo_paradas_ref
        
        custo_ref = (consumo_ref * preco_combustivel) + (tempo_total_ref * custo_motorista_hora)
        
        economia = custo_ref - custo_minimo
        economia_percentual = (economia / custo_ref) * 100 if custo_ref > 0 else 0
        
        # Cálculo dos custos no ponto ótimo
        tempo_otimo = distancia_km / velocidade_otima
        tempo_paradas_otimo = distancia_km * 0.02 if velocidade_otima < 40 else 0
        tempo_total_otimo = tempo_otimo + tempo_paradas_otimo
        
        # Fatores de consumo no ponto ótimo
        fator_otimo = 1.0
        if velocidade_otima < 30:
            fator_otimo = 1.4
        elif velocidade_otima < 50:
            fator_otimo = 1.2
        elif velocidade_otima > 70:
            fator_otimo = 1.3
            
        consumo_otimo = max(distancia_km / consumo_base_kmh, 0.05) * fator_otimo
        custo_combustivel_otimo = consumo_otimo * preco_combustivel
        custo_tempo_otimo = tempo_total_otimo * custo_motorista_hora
        
        # Análise de sensibilidade
        sensibilidade = []
        for delta in [-10, -5, 5, 10]:
            v_test = velocidade_otima + delta
            if v_min <= v_test <= v_max:
                t_test = distancia_km / v_test
                c_test = (max(distancia_km / consumo_base_kmh, 0.05) * 1.2 * preco_combustivel) + (t_test * custo_motorista_hora)
                diff = c_test - custo_minimo
                sensibilidade.append({
                    'variacao_velocidade': delta,
                    'nova_velocidade': round(v_test, 1),
                    'aumento_custo': round(diff, 2),
                    'aumento_percentual': round((diff/custo_minimo)*100, 1)
                })
        
        # Justificativa da escolha
        justificativa = f"Velocidade ótima de {velocidade_otima:.1f} km/h escolhida através de análise de {len(velocidades)} pontos na faixa {v_min}-{v_max} km/h. "
        justificativa += f"Esta velocidade minimiza a função de custo f(v) = {custo_minimo:.2f}, balanceando custo de combustível (R$ {custo_combustivel_otimo:.2f}) e custo de tempo (R$ {custo_tempo_otimo:.2f}). "
        
        if economia_percentual > 5:
            justificativa += f"Economia significativa de {economia_percentual:.1f}% comparado à velocidade de referência."
        elif economia_percentual > 0:
            justificativa += f"Economia moderada de {economia_percentual:.1f}% comparado à velocidade de referência."
        else:
            justificativa += "Velocidade de referência já próxima do ótimo."
        
        return {
            'velocidade_otima': round(velocidade_otima, 1),
            'custo_total': round(custo_minimo, 2),
            'economia_vs_40kmh': round(economia, 2),
            'economia_percentual': round(economia_percentual, 1),
            'grafico_dados': dados_grafico,
            'analise': {
                'justificativa': justificativa,
                'ponto_otimo': {
                    'velocidade': round(velocidade_otima, 1),
                    'custo_total': round(custo_minimo, 2),
                    'custo_combustivel': round(custo_combustivel_otimo, 2),
                    'custo_tempo': round(custo_tempo_otimo, 2),
                    'tempo_viagem': round(tempo_total_otimo, 3)
                },
                'sensibilidade': sensibilidade,
                'metodo': f"Otimização numérica discreta com {len(velocidades)} pontos",
                'restricoes': f"Velocidade limitada entre {v_min}-{v_max} km/h para distância de {distancia_km} km"
            },
            'cenario': {
                'distancia_km': distancia_km,
                'tempo_viagem_horas': round(tempo_total_otimo, 2),
                'consumo_estimado_litros': round(consumo_otimo, 2),
                'tipo_veiculo': tipo_veiculo,
                'tipo_rota': 'urbana',  # Sempre assumir urbana
                'custo_combustivel': round(custo_combustivel_otimo, 2),
                'custo_tempo': round(custo_tempo_otimo, 2),
                'faixa_velocidade': f"{v_min}-{v_max} km/h"
            }
        }

# Configuração do banco de dados SQLite
DB_PATH = "otimizacoes.db"

def init_database():
    """Inicializa o banco de dados SQLite"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela de otimizações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otimizacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            nome_veiculo TEXT NOT NULL,
            origem TEXT NOT NULL,
            destino TEXT NOT NULL,
            distancia_km REAL NOT NULL,
            velocidade_otima REAL NOT NULL,
            custo_total REAL NOT NULL,
            economia_rs REAL NOT NULL,
            economia_percentual REAL NOT NULL,
            tempo_viagem_horas REAL NOT NULL,
            preco_combustivel REAL NOT NULL,
            custo_motorista_hora REAL NOT NULL,
            analise_completa TEXT,
            dados_grafico TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Banco de dados SQLite inicializado")

# Verificar se a chave API foi configurada
if OPENROUTE_API_KEY == "YOUR_API_KEY_HERE":
    print("AVISO: Chave API do OpenRoute Service não configurada")
    print("   1. Copie o arquivo .env.example para .env")
    print("   2. Edite o arquivo .env e adicione sua chave API")
    print("   3. Registre-se gratuitamente em: https://openrouteservice.org/dev/#/signup")
else:
    print("Chave API do OpenRoute Service configurada")

# Inicializar banco de dados
init_database()

# Modelos Pydantic
class EnderecoModel(BaseModel):
    endereco: str = Field(..., description="Endereço completo")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    cidade: Optional[str] = Field(None, description="Cidade")

class RotaRequest(BaseModel):
    origem: EnderecoModel = Field(..., description="Endereço de origem")
    destino: EnderecoModel = Field(..., description="Endereço de destino")
    paradas_intermediarias: Optional[List[EnderecoModel]] = Field(default=[], description="Paradas no caminho")
    perfil_veiculo: Optional[str] = Field("driving-car", description="Perfil do veículo")

class OtimizacaoMapaRequest(BaseModel):
    rota: RotaRequest = Field(..., description="Dados da rota")
    nome_veiculo: str = Field(..., description="Nome do veículo (ex: 'Fiorino João', 'Van 01')")
    massa: float = Field(..., ge=1000, le=3500, description="Massa total do veículo em kg")
    preco_combustivel: float = Field(..., ge=3.0, le=10.0, description="Preço do combustível em R$/L")
    custo_hora_motorista: Optional[float] = Field(25.0, ge=10.0, le=100.0, description="Custo por hora do motorista")
    custo_hora_veiculo: Optional[float] = Field(15.0, ge=5.0, le=50.0, description="Custo por hora do veículo")
    veiculo: Optional[str] = Field("fiorino", description="Tipo de veículo da frota")
    combustivel_inicial: Optional[float] = Field(0.8, ge=0.1, le=1.0, description="Nível inicial de combustível")

class EnderecoResponse(BaseModel):
    endereco_formatado: str
    latitude: float
    longitude: float
    cidade: str
    estado: str
    confidence: Optional[float] = None
    match_type: Optional[str] = None

class RotaResponse(BaseModel):
    distancia_km: float
    tempo_estimado_horas: float
    velocidade_media_kmh: float
    tipo_via_predominante: str
    tem_pedagio: bool
    coordenadas_rota: List[List[float]]
    instrucoes: List[str]

# Classe para integração com mapas
class MapaService:
    def __init__(self):
        self.api_key = OPENROUTE_API_KEY
        self.base_url = OPENROUTE_BASE_URL
        
    async def geocodificar_endereco(self, endereco: str) -> Dict[str, Any]:
        """Converte endereço em coordenadas usando OpenRoute Service"""
        print(f"DEBUG GEOCODING - Endereco recebido: '{endereco}'")
        print(f"DEBUG GEOCODING - API Key: {self.api_key[:20]}...")
        
        if self.api_key == "YOUR_API_KEY_HERE":
            # Fallback com coordenadas fictícias para teste
            print("DEBUG GEOCODING - API Key não configurada, usando fallback")
            return {
                "endereco_formatado": endereco + " (sem API - São Paulo)",
                "latitude": -23.550520,  # São Paulo como exemplo
                "longitude": -46.633309,
                "cidade": "São Paulo",
                "estado": "SP"
            }
            
        # Verificar se é um endereço válido
        if len(endereco.strip()) < 5:
            print("DEBUG GEOCODING - Endereco muito curto")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_address_format",
                    "message": "Endereco muito curto ou incompleto",
                    "endereco_original": endereco,
                    "sugestao": "Forneca um endereco completo com pelo menos rua e cidade"
                }
            )
            
        async with httpx.AsyncClient() as client:
            try:
                # OpenRoute Service usa endpoint diferente para geocoding
                url = "https://api.openrouteservice.org/geocode/search"
                params = {
                    "api_key": self.api_key,
                    "text": endereco,
                    "boundary.country": "BR",
                    "size": 1
                }
                
                print(f"DEBUG GEOCODING - URL: {url}")
                print(f"DEBUG GEOCODING - Params: {params}")
                
                response = await client.get(url, params=params)
                print(f"DEBUG GEOCODING - Status: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                
                print(f"DEBUG GEOCODING - Resposta API: {data}")
                
                if data.get("features") and len(data["features"]) > 0:
                    feature = data["features"][0]
                    props = feature["properties"]
                    coords = feature["geometry"]["coordinates"]
                    
                    # Validar qualidade do geocoding
                    confidence = props.get("confidence", 0)
                    match_type = props.get("match_type", "unknown")
                    latitude = coords[1]
                    longitude = coords[0]
                    
                    print(f"DEBUG GEOCODING - Confidence: {confidence}, Match Type: {match_type}")
                    print(f"DEBUG GEOCODING - Coordenadas: [{longitude}, {latitude}]")
                    
                    # Validar se coordenadas estão dentro do Brasil (aproximadamente)
                    if not (-35.0 <= latitude <= 5.0 and -75.0 <= longitude <= -30.0):
                        print(f"DEBUG GEOCODING - Coordenadas fora do Brasil: [{longitude}, {latitude}]")
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "error": "geocoding_outside_brazil",
                                "message": "Endereco encontrado fora do territorio brasileiro",
                                "endereco_original": endereco,
                                "coordenadas": [longitude, latitude],
                                "sugestao": "Verifique se o endereco esta no Brasil e inclua cidade e estado"
                            }
                        )
                    
                    # Rejeitar apenas resultados muito ruins
                    # Para APIs gratuitas, ser mais permissivo
                    if confidence < 0.5:
                        error_msg = f"Endereco '{endereco}' nao encontrado. Confidence muito baixo: {confidence}"
                        print(f"DEBUG GEOCODING - {error_msg}")
                        raise HTTPException(
                            status_code=422, 
                            detail={
                                "error": "geocoding_very_low_quality",
                                "message": "Endereco nao encontrado com confianca minima",
                                "endereco_original": endereco,
                                "confidence": confidence,
                                "match_type": match_type,
                                "coordenadas": [longitude, latitude],
                                "sugestao": "Verifique se o endereco existe e esta correto"
                            }
                        )
                    
                    # Avisar sobre baixa qualidade mas aceitar
                    if confidence < 0.7 or match_type == "fallback":
                        print(f"DEBUG GEOCODING - AVISO: Baixa precisao mas aceitavel. Confidence: {confidence}, Tipo: {match_type}")
                    
                    # Adicionar aviso se qualidade for baixa
                    endereco_formatado = props.get("label", endereco)
                    if confidence < 0.7 or match_type == "fallback":
                        endereco_formatado += " (localizacao aproximada)"
                    
                    result = {
                        "endereco_formatado": endereco_formatado,
                        "latitude": coords[1],
                        "longitude": coords[0],
                        "cidade": props.get("locality", ""),
                        "estado": props.get("region", ""),
                        "confidence": confidence,
                        "match_type": match_type
                    }
                    print(f"DEBUG GEOCODING - Resultado validado: {result}")
                    return result
                else:
                    print("DEBUG GEOCODING - Nenhum resultado encontrado")
                    raise HTTPException(
                        status_code=404, 
                        detail={
                            "error": "geocoding_not_found",
                            "message": "Endereco nao encontrado",
                            "endereco_original": endereco,
                            "sugestao": "Verifique a formatacao do endereco e inclua detalhes como cidade, estado e CEP"
                        }
                    )
                    
            except httpx.RequestError as e:
                print(f"DEBUG GEOCODING - Erro de request: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Erro na consulta de geocodificação: {str(e)}")
            except Exception as e:
                print(f"DEBUG GEOCODING - Erro geral: {str(e)}")
                # Propagar o erro ao invés de usar fallback
                if "422:" in str(e):
                    # Re-propagar erros de validação
                    raise e
                else:
                    # Outros erros técnicos
                    raise HTTPException(
                        status_code=500, 
                        detail={
                            "error": "geocoding_service_error",
                            "message": "Erro no servico de geocoding",
                            "endereco_original": endereco,
                            "error_details": str(e)
                        }
                    ) # Procure digitar o máximo de informações possíveis no endereço, já que o modelo é afetado pela não tão alta precisão

    
    async def calcular_rota(self, origem: Dict, destino: Dict, paradas: List[Dict] = None,
                           perfil: str = "driving-car") -> Dict[str, Any]:
        """Calcula rota otimizada entre pontos"""
        if self.api_key == "YOUR_API_KEY_HERE":
            # Fallback com dados fictícios para teste
            distancia = abs(origem["latitude"] - destino["latitude"]) * 111  # Aproximação simples
            return {
                "distancia_km": round(distancia, 1),
                "tempo_estimado_horas": round(distancia / 50, 1),  # Assumindo 50km/h médio
                "velocidade_media_kmh": 50,
                "tipo_via_predominante": "urbana",
                "tem_pedagio": False,
                "coordenadas_rota": [[origem["longitude"], origem["latitude"]], 
                                   [destino["longitude"], destino["latitude"]]],
                "instrucoes": [f"Sair de {origem.get('endereco_formatado', 'origem')}", 
                             f"Chegar em {destino.get('endereco_formatado', 'destino')}"]
            }
            
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.base_url}/directions/{perfil}"
                
                # Montar coordenadas
                coordinates = [[origem["longitude"], origem["latitude"]]]
                if paradas:
                    for parada in paradas:
                        coordinates.append([parada["longitude"], parada["latitude"]])
                coordinates.append([destino["longitude"], destino["latitude"]])
                
                payload = {
                    "coordinates": coordinates,
                    "format": "json",
                    "instructions": True,
                    "maneuvers": True
                }
                
                headers = {
                    "Authorization": self.api_key,
                    "Content-Type": "application/json"
                }
                
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                print(f"DEBUG - Resposta da API: {data}")  # Debug
                
                if data.get("routes") and len(data["routes"]) > 0:
                    route = data["routes"][0]
                    summary = route.get("summary", {})
                    
                    print(f"DEBUG - Summary: {summary}")  # Debug
                    
                    # Extrair distância e duração com verificação de campos
                    distance_m = summary.get("distance", 0)
                    duration_s = summary.get("duration", 0)
                    
                    if distance_m == 0 or duration_s == 0:
                        # Tentar campos alternativos
                        segments = route.get("segments", [])
                        if segments:
                            distance_m = sum(seg.get("distance", 0) for seg in segments)
                            duration_s = sum(seg.get("duration", 0) for seg in segments)
                    
                    # Analisar tipo de via predominante
                    segments = route.get("segments", [])
                    via_urbana = any("city" in str(seg).lower() or "urban" in str(seg).lower() 
                                   for seg in segments)
                    
                    # Extrair coordenadas da rota
                    geometry = route.get("geometry")
                    coordenadas_rota = []
                    if geometry:
                        if isinstance(geometry, dict) and "coordinates" in geometry:
                            coordenadas_rota = geometry["coordinates"]
                        elif isinstance(geometry, str):
                            # Geometry vem como polyline codificada, usar pontos simples
                            # Para simplificar, criar rota aproximada com pontos de origem e destino
                            coordenadas_rota = [
                                [origem["longitude"], origem["latitude"]],
                                [destino["longitude"], destino["latitude"]]
                            ]
                    
                    # Se não temos coordenadas, usar origem e destino
                    if not coordenadas_rota:
                        coordenadas_rota = [
                            [origem["longitude"], origem["latitude"]],
                            [destino["longitude"], destino["latitude"]]
                        ]
                    
                    return {
                        "distancia_km": round(distance_m / 1000, 1) if distance_m > 0 else 0,
                        "tempo_estimado_horas": round(duration_s / 3600, 2) if duration_s > 0 else 0,
                        "velocidade_media_kmh": round((distance_m / 1000) / (duration_s / 3600), 1) if distance_m > 0 and duration_s > 0 else 0,
                        "tipo_via_predominante": "urbana" if via_urbana else "interior",
                        "tem_pedagio": False,
                        "coordenadas_rota": coordenadas_rota,
                        "instrucoes": []  # Lista vazia pois essas informações são inacessíveis por enquanto
                    }
                else:
                    raise HTTPException(status_code=404, detail="Rota não encontrada")
                    
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Erro no cálculo da rota: {str(e)}")



# Inicializar serviços
app = FastAPI(title="Otimizador com Mapas", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mapa_service = MapaService()
otimizador = OtimizadorCombustivel()

# Endpoints
@app.get("/")
async def root():
    return {"message": "Sistema de Otimização com Mapas funcionando", "version": "2.0.0"}

@app.post("/geocodificar", response_model=EnderecoResponse)
async def geocodificar_endereco(endereco: str):
    """Converte endereço em coordenadas"""
    resultado = await mapa_service.geocodificar_endereco(endereco)
    return EnderecoResponse(**resultado)

@app.post("/calcular-rota", response_model=RotaResponse)
async def calcular_rota(rota_request: RotaRequest):
    """Calcula rota entre dois pontos"""
    try:
        # Geocodificar origem se necessário
        if not rota_request.origem.latitude:
            print(f"DEBUG - Geocodificando origem: {rota_request.origem.endereco}")
            origem_geo = await mapa_service.geocodificar_endereco(rota_request.origem.endereco)
        else:
            origem_geo = rota_request.origem.dict()
        
        # Geocodificar destino se necessário
        if not rota_request.destino.latitude:
            print(f"DEBUG - Geocodificando destino: {rota_request.destino.endereco}")
            destino_geo = await mapa_service.geocodificar_endereco(rota_request.destino.endereco)
        else:
            destino_geo = rota_request.destino.dict()
            
    except HTTPException as e:
        # Re-propagar erros de geocoding com contexto adicional
        error_detail = e.detail.copy() if isinstance(e.detail, dict) else {"message": str(e.detail)}
        
        if hasattr(e.detail, 'get') and e.detail.get('error') in ['geocoding_low_quality', 'geocoding_not_found', 'geocoding_outside_brazil', 'geocoding_service_error']:
            error_detail['context'] = 'Erro ao calcular rota - problema no geocoding de enderecos'
            error_detail['instrucoes'] = [
                "Verifique se o endereco esta completo com rua, numero, bairro, cidade e estado",
                "Use formatacao brasileira padrao (ex: Rua das Flores, 123 - Centro, São Paulo - SP)",
                "Inclua o CEP quando possivel para maior precisao"
            ]
        
        raise HTTPException(status_code=e.status_code, detail=error_detail)
    
    # Validar distância aproximada entre origem e destino
    import math
    
    def distancia_haversine(lat1, lon1, lat2, lon2):
        """Calcula distância aproximada entre dois pontos em km"""
        R = 6371  # Raio da Terra em km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    distancia_direta = distancia_haversine(
        origem_geo["latitude"], origem_geo["longitude"],
        destino_geo["latitude"], destino_geo["longitude"]
    )
    
    print(f"DEBUG - Distancia direta origem-destino: {distancia_direta:.2f} km")
    
    # Rejeitar rotas muito longas que podem indicar erro de geocoding
    if distancia_direta > 2000:  # Mais de 2000km indica possível erro
        raise HTTPException(
            status_code=422,
            detail={
                "error": "route_too_long",
                "message": "Distancia entre origem e destino muito grande",
                "distancia_km": round(distancia_direta, 2),
                "origem": origem_geo.get("endereco_formatado", ""),
                "destino": destino_geo.get("endereco_formatado", ""),
                "sugestao": "Verifique se os enderecos estao corretos e na mesma regiao"
            }
        )
    
    print(f"DEBUG - Validacoes de geocoding passaram. Calculando rota...")
    print(f"DEBUG - Origem: {origem_geo.get('endereco_formatado', '')}")
    print(f"DEBUG - Destino: {destino_geo.get('endereco_formatado', '')}")
    
    # Calcular rota
    rota = await mapa_service.calcular_rota(origem_geo, destino_geo, 
                                          rota_request.paradas_intermediarias,
                                          rota_request.perfil_veiculo)
    
    return RotaResponse(**rota)

@app.post("/otimizar-com-mapa")
async def otimizar_com_mapa(request: OtimizacaoMapaRequest):
    """Otimização completa usando dados de mapa"""
    
    try:
        # 1. Calcular rota
        rota_calculada = await calcular_rota(request.rota)
        
        print(f"DEBUG OTIMIZAÇÃO - Rota calculada: {rota_calculada}")
        
        # 2. Criar otimizador
        otimizador = OtimizadorCombustivel()
        
        # 3. Mapear tipo de veículo para consumo
        veiculos_consumo = {
            "fiorino": 12.0,
            "expert": 10.0,
            "transit": 8.0
        }
        
        consumo_veiculo = veiculos_consumo.get(request.veiculo, 12.0)
        
        # 4. Otimizar velocidade
        resultado = otimizador.otimizar_velocidade(
            distancia_km=rota_calculada.distancia_km,
            massa_kg=request.massa,
            preco_combustivel=request.preco_combustivel,
            consumo_base_kmh=consumo_veiculo,
            custo_motorista_hora=request.custo_hora_motorista,
            tipo_rota="urbana",  # Sempre usar urbana
            tipo_veiculo=request.veiculo,
            paradas=5,
            nivel_combustivel=request.combustivel_inicial
        )
        
        # 5. Enriquecer com dados da rota
        resultado['rota_info'] = {
            'nome_veiculo': request.nome_veiculo,
            'distancia_km': rota_calculada.distancia_km,
            'tempo_estimado_horas': rota_calculada.tempo_estimado_horas,
            'velocidade_media_sugerida': rota_calculada.velocidade_media_kmh,
            'tipo_via': rota_calculada.tipo_via_predominante,
            'tem_pedagio': rota_calculada.tem_pedagio,
            'origem': request.rota.origem.endereco,
            'destino': request.rota.destino.endereco,
            'coordenadas_rota': rota_calculada.coordenadas_rota
        }
        
        # 6. Salvar no banco de dados
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO otimizacoes (
                    nome_veiculo, origem, destino, distancia_km, velocidade_otima, 
                    custo_total, economia_rs, economia_percentual, tempo_viagem_horas,
                    preco_combustivel, custo_motorista_hora, analise_completa, dados_grafico
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request.nome_veiculo,
                request.rota.origem.endereco,
                request.rota.destino.endereco,
                rota_calculada.distancia_km,
                resultado['velocidade_otima'],
                resultado['custo_total'],
                resultado['economia_vs_40kmh'],
                resultado['economia_percentual'],
                resultado['cenario']['tempo_viagem_horas'],
                request.preco_combustivel,
                request.custo_hora_motorista,
                json.dumps(resultado['analise'], ensure_ascii=False),
                json.dumps(resultado['grafico_dados'], ensure_ascii=False)
            ))
            
            conn.commit()
            conn.close()
            print(f"Otimização salva no banco: {request.nome_veiculo}")
        except Exception as e:
            print(f"Erro ao salvar no banco: {str(e)}")
        
        return resultado
        
    except Exception as e:
        print(f"DEBUG OTIMIZAÇÃO - Erro: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro na otimização: {str(e)}")

@app.get("/historico")
async def obter_historico(limit: int = 10):
    """Obtém histórico de otimizações"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, data_hora, nome_veiculo, origem, destino, distancia_km,
                   velocidade_otima, custo_total, economia_rs, economia_percentual,
                   tempo_viagem_horas, preco_combustivel
            FROM otimizacoes
            ORDER BY data_hora DESC
            LIMIT ?
        ''', (limit,))
        
        resultados = cursor.fetchall()
        conn.close()
        
        historico = []
        for row in resultados:
            historico.append({
                'id': row[0],
                'data_hora': row[1],
                'nome_veiculo': row[2],
                'origem': row[3],
                'destino': row[4],
                'distancia_km': row[5],
                'velocidade_otima': row[6],
                'custo_total': row[7],
                'economia_rs': row[8],
                'economia_percentual': row[9],
                'tempo_viagem_horas': row[10],
                'preco_combustivel': row[11]
            })
            
        return {'historico': historico}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar histórico: {str(e)}")

@app.get("/estatisticas")
async def obter_estatisticas():
    """Obtém estatísticas gerais de economia"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Estatísticas gerais
        cursor.execute('''
            SELECT 
                COUNT(*) as total_otimizacoes,
                SUM(economia_rs) as economia_total_rs,
                AVG(economia_rs) as economia_media_rs,
                AVG(economia_percentual) as economia_media_pct,
                SUM(distancia_km) as distancia_total_km,
                COUNT(DISTINCT nome_veiculo) as veiculos_diferentes
            FROM otimizacoes
        ''')
        
        stats = cursor.fetchone()
        
        # Top 5 veículos por economia
        cursor.execute('''
            SELECT nome_veiculo, COUNT(*) as viagens, SUM(economia_rs) as economia_total
            FROM otimizacoes
            GROUP BY nome_veiculo
            ORDER BY economia_total DESC
            LIMIT 5
        ''')
        
        top_veiculos = cursor.fetchall()
        conn.close()
        
        return {
            'estatisticas_gerais': {
                'total_otimizacoes': stats[0] or 0,
                'economia_total_rs': round(stats[1] or 0, 2),
                'economia_media_rs': round(stats[2] or 0, 2),
                'economia_media_percentual': round(stats[3] or 0, 1),
                'distancia_total_km': round(stats[4] or 0, 1),
                'veiculos_diferentes': stats[5] or 0
            },
            'top_veiculos': [{
                'nome': veiculo[0],
                'viagens': veiculo[1],
                'economia_total': round(veiculo[2], 2)
            } for veiculo in top_veiculos]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar estatísticas: {str(e)}")

if __name__ == "__main__":
    print("Iniciando Sistema de Otimização com Mapas...")
    print("OpenRoute Service integrado")
    print("Para usar com mapas e rotas reais, registre uma chave em: https://openrouteservice.org/dev/#/signup")
    
    # Usar porta 8000 padrão para evitar conflitos
    # Caso a porta esteja ocupada, altere para uma disponível
    uvicorn.run(app, host="0.0.0.0", port=8000)
