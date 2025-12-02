import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { Truck, MapPin, Navigation, Calculator, BarChart3, Route } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import './App.css';

// Fix para ícones do Leaflet
import L from 'leaflet';
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [formData, setFormData] = useState({
    origem: '',
    destino: '',
    nome_veiculo: '',
    massa: 1500,
    preco_combustivel: 5.50,
    custo_hora_motorista: 25.0,
    custo_hora_veiculo: 15.0,
    veiculo: 'fiorino',
    combustivel_inicial: 0.8
  });


  
  const [rotaCalculada, setRotaCalculada] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [historico, setHistorico] = useState([]);
  const [estatisticas, setEstatisticas] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('rota');
  const [mapaCenter, setMapaCenter] = useState([-23.550520, -46.633309]); // São Paulo
  const [coordenadasRota, setCoordenadasRota] = useState([]);
  const [markersRota, setMarkersRota] = useState([]);

  const mapRef = useRef();

  const buscarHistorico = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/historico?limit=20`);
      setHistorico(response.data.historico);
    } catch (error) {
      console.error('Erro ao buscar histórico:', error);
    }
  };

  const buscarEstatisticas = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/estatisticas`);
      setEstatisticas(response.data);
    } catch (error) {
      console.error('Erro ao buscar estatísticas:', error);
    }
  };

  useEffect(() => {
    // Carregar histórico e estatísticas ao iniciar
    buscarHistorico();
    buscarEstatisticas();
  }, []);

  const handleInputChange = (e) => {
    const { name, value, type } = e.target;
    let processedValue = type === 'number' || type === 'range' ? parseFloat(value) || 0 : value;
    
    setFormData(prev => ({
      ...prev,
      [name]: processedValue
    }));
  };





  const calcularRota = async () => {
    if (!formData.origem || !formData.destino) {
      setError('Preencha origem e destino');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API_BASE_URL}/calcular-rota`, {
        origem: { endereco: formData.origem },
        destino: { endereco: formData.destino },
        paradas_intermediarias: [],
        perfil_veiculo: "driving-car"
      });

      setRotaCalculada(response.data);
      
      // Atualizar mapa
      if (response.data.coordenadas_rota) {
        const coordenadas = response.data.coordenadas_rota.map(coord => [coord[1], coord[0]]);
        setCoordenadasRota(coordenadas);
        
        if (coordenadas.length > 0) {
          setMapaCenter(coordenadas[0]);
          setMarkersRota([
            { position: coordenadas[0], popup: 'Origem' },
            { position: coordenadas[coordenadas.length - 1], popup: 'Destino' }
          ]);
        }
      }

    } catch (err) {
      setError('Erro ao calcular rota: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const otimizarComMapa = async () => {
    if (!rotaCalculada) {
      setError('Calcule a rota primeiro');
      return;
    }

    if (!formData.nome_veiculo.trim()) {
      setError('Informe o nome do veículo');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API_BASE_URL}/otimizar-com-mapa`, {
        rota: {
          origem: { endereco: formData.origem },
          destino: { endereco: formData.destino },
          paradas_intermediarias: [],
          perfil_veiculo: "driving-car"
        },
        nome_veiculo: formData.nome_veiculo,
        massa: formData.massa,
        preco_combustivel: formData.preco_combustivel,
        custo_hora_motorista: formData.custo_hora_motorista,
        custo_hora_veiculo: formData.custo_hora_veiculo,
        veiculo: formData.veiculo,
        combustivel_inicial: formData.combustivel_inicial
      });

      setResultado(response.data);
      
      // Atualizar histórico e estatísticas após nova otimização
      buscarHistorico();
      buscarEstatisticas();
    } catch (err) {
      setError('Erro na otimização: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const prepararDadosGrafico = () => {
    if (!resultado?.grafico_dados) return null;

    const velocidades = resultado.grafico_dados.map(item => item.velocidade);
    const custos = resultado.grafico_dados.map(item => item.custo_total);
    
    const custoMinimo = Math.min(...custos);
    const indiceOtimo = custos.findIndex(custo => custo === custoMinimo);
    
    const pontosRadius = resultado.grafico_dados.map((_, index) => 
      index === indiceOtimo ? 12 : 3
    );
    
    const pontosCores = resultado.grafico_dados.map((_, index) => 
      index === indiceOtimo ? '#ff4444' : 'rgb(102, 126, 234)'
    );

    return {
      labels: velocidades,
      datasets: [{
        label: 'Custo Total (R$)',
        data: custos,
        borderColor: 'rgb(102, 126, 234)',
        backgroundColor: 'rgba(102, 126, 234, 0.1)',
        borderWidth: 2,
        pointRadius: pontosRadius,
        pointBackgroundColor: pontosCores,
        pointBorderColor: pontosCores,
        pointBorderWidth: 2,
        tension: 0.1
      }]
    };
  };

  const opcoesGrafico = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' },
      title: {
        display: true,
        text: 'Otimização de Velocidade (Ponto Vermelho = Ótimo)'
      }
    },
    scales: {
      x: { title: { display: true, text: 'Velocidade (km/h)' } },
      y: { title: { display: true, text: 'Custo (R$)' } }
    }
  };

  return (
    <div className="container">
      <header className="header">
        <h1><Truck className="inline-icon" /> Otimizador com Mapas</h1>
        <p>Sistema de Otimização de Combustível com Cálculo Automático de Rotas</p>
      </header>

      <nav className="tabs">
        <button 
          className={`tab-button ${activeTab === 'rota' ? 'active' : ''}`}
          onClick={() => setActiveTab('rota')}
        >
          <Route size={16} /> Calcular Rota
        </button>
        <button 
          className={`tab-button ${activeTab === 'otimizar' ? 'active' : ''}`}
          onClick={() => setActiveTab('otimizar')}
        >
          <Calculator size={16} /> Otimizar
        </button>
        <button 
          className={`tab-button ${activeTab === 'mapa' ? 'active' : ''}`}
          onClick={() => setActiveTab('mapa')}
        >
          <MapPin size={16} /> Visualizar Mapa
        </button>
        <button 
          className={`tab-button ${activeTab === 'grafico' ? 'active' : ''}`}
          onClick={() => setActiveTab('grafico')}
        >
          <BarChart3 size={16} /> Gráfico
        </button>
        <button 
          className={`tab-button ${activeTab === 'historico' ? 'active' : ''}`}
          onClick={() => setActiveTab('historico')}
        >
          📋 Histórico
        </button>
        <button 
          className={`tab-button ${activeTab === 'estatisticas' ? 'active' : ''}`}
          onClick={() => setActiveTab('estatisticas')}
        >
          📊 Estatísticas
        </button>
      </nav>

      {/* Tab: Calcular Rota */}
      {activeTab === 'rota' && (
        <div className="card">
          <h2 style={{marginBottom: '20px'}}>
            <Route className="inline-icon" /> Definir Rota
          </h2>

          <div className="form-group">
            <label htmlFor="origem">📍 Endereço de Origem</label>
            <input
              type="text"
              id="origem"
              name="origem"
              value={formData.origem}
              onChange={handleInputChange}
              placeholder="Ex: Rua das Flores, 123 - Centro, São Paulo - SP"
              autoComplete="off"
              required
            />

          </div>

          <div className="form-group">
            <label htmlFor="destino">🏁 Endereço de Destino</label>
            <input
              type="text"
              id="destino"
              name="destino"
              value={formData.destino}
              onChange={handleInputChange}
              placeholder="Ex: Av. Paulista, 1000 - Bela Vista, São Paulo - SP"
              autoComplete="off"
              required
            />

          </div>

          <button 
            onClick={calcularRota}
            disabled={loading}
            className="btn-primary"
          >
            <Navigation className="inline-icon" />
            {loading ? 'Calculando...' : 'Calcular Rota'}
          </button>

          {rotaCalculada && (
            <div className="resultado-rota">
              <h3>✅ Rota Calculada</h3>
              <div className="info-grid">
                <div><strong>Distância:</strong> {rotaCalculada.distancia_km} km</div>
                <div><strong>Tempo:</strong> {rotaCalculada.tempo_estimado_horas} h</div>
                <div><strong>Velocidade Média:</strong> {rotaCalculada.velocidade_media_kmh} km/h</div>
                <div><strong>Tipo de Via:</strong> {rotaCalculada.tipo_via_predominante}</div>
              </div>
            </div>
          )}

          {error && <div className="error">{error}</div>}
        </div>
      )}

      {/* Tab: Otimizar */}
      {activeTab === 'otimizar' && (
        <div className="card">
          <h2><Calculator className="inline-icon" /> Otimização de Combustível</h2>
          
          <div className="form-group">
            <label htmlFor="nome_veiculo">🚛 Nome do Veículo</label>
            <input
              type="text"
              id="nome_veiculo"
              name="nome_veiculo"
              value={formData.nome_veiculo}
              onChange={handleInputChange}
              placeholder="Ex: Fiorino João, Van 01, Caminhão A"
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="massa">Massa do Veículo (kg)</label>
            <input
              type="number"
              id="massa"
              name="massa"
              value={formData.massa}
              onChange={handleInputChange}
              min="1000"
              max="3500"
            />
          </div>

          <div className="form-group">
            <label htmlFor="preco_combustivel">Preço Combustível (R$/L)</label>
            <input
              type="number"
              id="preco_combustivel"
              name="preco_combustivel"
              value={formData.preco_combustivel}
              onChange={handleInputChange}
              min="3"
              max="10"
              step="0.01"
            />
          </div>

          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px'}}>
            <div className="form-group">
              <label htmlFor="custo_hora_motorista">Custo/Hora Motorista (R$)</label>
              <input
                type="number"
                id="custo_hora_motorista"
                name="custo_hora_motorista"
                value={formData.custo_hora_motorista}
                onChange={handleInputChange}
                min="10"
                max="100"
                step="0.50"
              />
            </div>

            <div className="form-group">
              <label htmlFor="custo_hora_veiculo">Custo/Hora Veículo (R$)</label>
              <input
                type="number"
                id="custo_hora_veiculo"
                name="custo_hora_veiculo"
                value={formData.custo_hora_veiculo}
                onChange={handleInputChange}
                min="5"
                max="50"
                step="0.50"
              />
            </div>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px'}}>
            <div className="form-group">
              <label htmlFor="veiculo">Veículo da Frota</label>
              <select
                id="veiculo"
                name="veiculo"
                value={formData.veiculo}
                onChange={handleInputChange}
                style={{padding: '10px', border: '1px solid #ddd', borderRadius: '4px'}}
              >
                <option value="fiorino">🚐 Fiat Fiorino</option>
                <option value="expert">🚚 Peugeot Expert</option>
                <option value="transit">🚛 Ford Transit</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="combustivel_inicial">Nível Combustível (%)</label>
              <input
                type="range"
                id="combustivel_inicial"
                name="combustivel_inicial"
                value={formData.combustivel_inicial}
                onChange={handleInputChange}
                min="0.1"
                max="1.0"
                step="0.1"
                style={{width: '100%'}}
              />
              <div style={{textAlign: 'center', fontSize: '14px', marginTop: '5px'}}>
                {Math.round(formData.combustivel_inicial * 100)}% do tanque
              </div>
            </div>
          </div>

          <button 
            onClick={otimizarComMapa}
            disabled={loading || !rotaCalculada}
            className="btn-primary"
          >
            <Calculator className="inline-icon" />
            {loading ? 'Otimizando...' : 'Otimizar Velocidade'}
          </button>

          {!rotaCalculada && (
            <div className="warning">⚠️ Primeiro calcule uma rota na aba "Calcular Rota"</div>
          )}

          {resultado && (
            <div className="resultado-card">
              <h3>🎯 Resultado da Otimização - {resultado.rota_info?.nome_veiculo}</h3>
              <div className="resultado-grid">
                <div className="resultado-item">
                  <span className="valor">{resultado.velocidade_otima} km/h</span>
                  <span className="label">Velocidade Ótima</span>
                </div>
                <div className="resultado-item">
                  <span className="valor">R$ {resultado.custo_total}</span>
                  <span className="label">Custo Total</span>
                </div>
                <div className="resultado-item">
                  <span className="valor">R$ {resultado.economia_vs_40kmh}</span>
                  <span className="label">Economia vs 40km/h</span>
                </div>
                <div className="resultado-item">
                  <span className="valor">{resultado.economia_percentual}%</span>
                  <span className="label">Economia Percentual</span>
                </div>
              </div>
              
              {resultado.analise && (
                <div className="analise-completa">
                  <h4>📋 Análise da Solução</h4>
                  <div className="justificativa">
                    <p><strong>Justificativa:</strong></p>
                    <p>{resultado.analise.justificativa}</p>
                  </div>
                  
                  <div className="ponto-otimo">
                    <h5>🎯 Ponto Ótimo</h5>
                    <div className="info-grid">
                      <div><strong>Velocidade:</strong> {resultado.analise.ponto_otimo.velocidade} km/h</div>
                      <div><strong>f(v) =</strong> R$ {resultado.analise.ponto_otimo.custo_total}</div>
                      <div><strong>Combustível:</strong> R$ {resultado.analise.ponto_otimo.custo_combustivel}</div>
                      <div><strong>Tempo:</strong> R$ {resultado.analise.ponto_otimo.custo_tempo}</div>
                    </div>
                  </div>
                  
                  {resultado.analise.sensibilidade && resultado.analise.sensibilidade.length > 0 && (
                    <div className="sensibilidade">
                      <h5>⚖️ Análise de Sensibilidade</h5>
                      <div className="sensibilidade-grid">
                        {resultado.analise.sensibilidade.map((sens, index) => (
                          <div key={index} className="sensibilidade-item">
                            <span>{sens.nova_velocidade} km/h</span>
                            <span className={sens.aumento_custo > 0 ? 'negativo' : 'positivo'}>
                              {sens.aumento_custo > 0 ? '+' : ''}R$ {sens.aumento_custo}
                              ({sens.aumento_percentual > 0 ? '+' : ''}{sens.aumento_percentual}%)
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <div className="metodo-info">
                    <p><strong>Método:</strong> {resultado.analise.metodo}</p>
                    <p><strong>Restrições:</strong> {resultado.analise.restricoes}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {error && <div className="error">{error}</div>}
        </div>
      )}

      {/* Tab: Mapa */}
      {activeTab === 'mapa' && (
        <div className="card">
          <h2><MapPin className="inline-icon" /> Visualização da Rota</h2>
          
          <div className="mapa-container" style={{height: '500px', width: '100%'}}>
            <MapContainer 
              center={mapaCenter} 
              zoom={13} 
              style={{height: '100%', width: '100%'}}
              ref={mapRef}
            >
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              />
              
              {markersRota.map((marker, index) => (
                <Marker key={index} position={marker.position}>
                  <Popup>{marker.popup}</Popup>
                </Marker>
              ))}
              
              {coordenadasRota.length > 0 && (
                <Polyline 
                  positions={coordenadasRota}
                  color="blue"
                  weight={4}
                  opacity={0.7}
                />
              )}
            </MapContainer>
          </div>

          {!rotaCalculada && (
            <div className="info">
              <p>📍 Primeiro calcule uma rota para visualizar no mapa</p>
            </div>
          )}
        </div>
      )}

      {/* Tab: Gráfico */}
      {activeTab === 'grafico' && (
        <div className="card">
          <h2><BarChart3 className="inline-icon" /> Análise Gráfica</h2>
          
          {resultado && prepararDadosGrafico() ? (
            <div>
              <div style={{marginBottom: '15px', padding: '12px', backgroundColor: '#f0f8ff', borderRadius: '8px'}}>
                🎯 <strong>Velocidade Ótima:</strong> {resultado.velocidade_otima} km/h | 
                💰 <strong>Custo Mínimo:</strong> R$ {resultado.custo_minimo}
              </div>
              <div style={{height: '400px', position: 'relative'}}>
                <Line 
                  key={`grafico-${resultado.velocidade_otima}`}
                  data={prepararDadosGrafico()} 
                  options={opcoesGrafico} 
                />
              </div>
            </div>
          ) : (
            <div style={{textAlign: 'center', padding: '40px', color: '#666'}}>
              <BarChart3 size={64} style={{opacity: 0.3, marginBottom: '15px'}} />
              <p>Execute uma otimização para visualizar o gráfico</p>
            </div>
          )}
        </div>
      )}

      {/* Tab: Histórico */}
      {activeTab === 'historico' && (
        <div className="card">
          <h2>📋 Histórico de Otimizações</h2>
          
          <button 
            onClick={buscarHistorico}
            className="btn-secondary"
            style={{marginBottom: '20px'}}
          >
            🔄 Atualizar Histórico
          </button>
          
          {historico.length > 0 ? (
            <div className="historico-lista">
              {historico.map((item) => (
                <div key={item.id} className="historico-item">
                  <div className="historico-header">
                    <h4>{item.nome_veiculo}</h4>
                    <span className="data">{new Date(item.data_hora).toLocaleString('pt-BR')}</span>
                  </div>
                  <div className="historico-rota">
                    <p><strong>De:</strong> {item.origem}</p>
                    <p><strong>Para:</strong> {item.destino}</p>
                  </div>
                  <div className="historico-resultado">
                    <div className="info-grid">
                      <div><strong>Distância:</strong> {item.distancia_km} km</div>
                      <div><strong>Velocidade Ótima:</strong> {item.velocidade_otima} km/h</div>
                      <div><strong>Custo Total:</strong> R$ {item.custo_total}</div>
                      <div><strong>Economia:</strong> R$ {item.economia_rs} ({item.economia_percentual}%)</div>
                      <div><strong>Tempo:</strong> {item.tempo_viagem_horas}h</div>
                      <div><strong>Combustível:</strong> R$ {item.preco_combustivel}/L</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p>📭 Nenhuma otimização registrada ainda.</p>
              <p>Faça sua primeira otimização na aba "Otimizar"!</p>
            </div>
          )}
        </div>
      )}

      {/* Tab: Estatísticas */}
      {activeTab === 'estatisticas' && (
        <div className="card">
          <h2>📊 Estatísticas de Economia</h2>
          
          <button 
            onClick={buscarEstatisticas}
            className="btn-secondary"
            style={{marginBottom: '20px'}}
          >
            🔄 Atualizar Estatísticas
          </button>
          
          {estatisticas ? (
            <div className="estatisticas-container">
              <div className="estatisticas-gerais">
                <h3>🌍 Estatísticas Gerais</h3>
                <div className="stats-grid">
                  <div className="stat-item">
                    <span className="stat-valor">{estatisticas.estatisticas_gerais.total_otimizacoes}</span>
                    <span className="stat-label">Otimizações Realizadas</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-valor">R$ {estatisticas.estatisticas_gerais.economia_total_rs}</span>
                    <span className="stat-label">Economia Total Acumulada</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-valor">R$ {estatisticas.estatisticas_gerais.economia_media_rs}</span>
                    <span className="stat-label">Economia Média por Viagem</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-valor">{estatisticas.estatisticas_gerais.economia_media_percentual}%</span>
                    <span className="stat-label">Economia Percentual Média</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-valor">{estatisticas.estatisticas_gerais.distancia_total_km} km</span>
                    <span className="stat-label">Distância Total Otimizada</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-valor">{estatisticas.estatisticas_gerais.veiculos_diferentes}</span>
                    <span className="stat-label">Veículos Diferentes</span>
                  </div>
                </div>
              </div>
              
              {estatisticas.top_veiculos.length > 0 && (
                <div className="top-veiculos">
                  <h3>🏆 Top 5 Veículos por Economia</h3>
                  <div className="ranking-lista">
                    {estatisticas.top_veiculos.map((veiculo, index) => (
                      <div key={index} className="ranking-item">
                        <span className="posicao">#{index + 1}</span>
                        <div className="veiculo-info">
                          <h4>{veiculo.nome}</h4>
                          <p>{veiculo.viagens} viagens</p>
                        </div>
                        <div className="economia-info">
                          <span className="economia-total">R$ {veiculo.economia_total}</span>
                          <span className="economia-por-viagem">R$ {(veiculo.economia_total / veiculo.viagens).toFixed(2)}/viagem</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="loading">Carregando estatísticas...</div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
