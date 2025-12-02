# Sistema de Otimização de Combustível com Mapas

Sistema integrado de otimização de rotas de entrega que combina modelagem matemática com APIs de geocodificação para minimizar custos totais de combustível e tempo de motorista.

## Descrição

O sistema implementa um modelo matemático por partes que considera fatores urbanos, tempo de paradas em semáforos e custos operacionais variáveis. A abordagem diferencia-se de métodos tradicionais por otimizar custos totais ao invés de apenas distância ou tempo de viagem.

### Principais características:
- Função objetivo por partes com validação matemática rigorosa
- Integração com APIs de geocodificação e roteamento (OpenRouteService)
- Sistema de validação de qualidade para evitar rotas incorretas
- Interface web para entrada de dados e visualização de resultados
- Análise de sensibilidade e comparação com métodos convencionais

## Requisitos

### Sistema Operacional
- Windows 10+
- Linux/macOS

### Software Necessário
- Python 3.8+
- Node.js 14+
- npm 6+

### Dependências Python
- FastAPI
- uvicorn
- httpx
- python-dotenv
- numpy
- sympy
- matplotlib
- jupyter

### API Externa
- Chave gratuita OpenRouteService (1000 requests/dia)
- Registro em: https://openrouteservice.org/dev/#/signup

## Tutorial de Instalação e Execução

### 1. Clonar Repositório
```bash
git clone <URL_DO_REPOSITORIO>
cd otimizador_com_mapas
```

### 2. Configurar Ambiente Python
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configurar Frontend
```bash
cd frontend
npm install
```

### 4. Configurar API de Mapas (Opcional)
```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar .env e substituir:
OPENROUTE_API_KEY=SUA_CHAVE_API_AQUI
```

### 5. Executar Sistema

#### Método Automático (Windows)
```cmd
iniciar.bat
```

#### Método Manual
```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend  
cd frontend
npm start
```

### 6. Acessar Aplicação
- Frontend: http://localhost:3000
- API Backend: http://localhost:8000
- Documentação API: http://localhost:8000/docs

## Exemplos de Uso

### Interface Web
1. Acesse http://localhost:3000
2. Insira endereços de origem e destino
3. Configure parâmetros (preço combustível, custo motorista, consumo base)
4. Execute otimização para obter velocidade recomendada

### API Direta
```bash
curl -X POST "http://localhost:8000/calcular-rota" \
  -H "Content-Type: application/json" \
  -d '{
    "origem": {"endereco": "Rua Princesa Isabel, Vila Belmiro, Santos"},
    "destino": {"endereco": "Comendador Nestor Pereira, Canindé, São Paulo"},
    "parametros": {
      "preco_combustivel": 5.5,
      "custo_hora_motorista": 20,
      "consumo_base_kmh": 12
    }
  }'
```

### Experimentos Matemáticos com SymPy

O arquivo `analise_matematica.ipynb` contém a fundamentação matemática completa do sistema.

#### Para reproduzir experimentos:
```bash
# Instalar Jupyter
pip install jupyter notebook

# Executar notebook
jupyter notebook analise_matematica.ipynb
```

#### Experimentos disponíveis:
- Análise de derivadas e pontos críticos
- Comparação modelo teórico vs. implementação prática
- Análise de sensibilidade dos parâmetros
- Validação de consistência numérica
- Visualização gráfica das funções de custo

#### Modificar parâmetros para novos experimentos:
```python
# No notebook, altere os valores base:
d_base = 10          # distância (km)
p_base = 5.5         # preço combustível (R$/l)
h_base = 20          # custo motorista (R$/h)
consumo_base = 12    # eficiência veículo (km/l)
```

## Estrutura do Projeto

```
otimizador_com_mapas/
├── README.md                    # Este arquivo
├── .gitignore                  # Arquivos ignorados pelo Git
├── .env.example                # Template de configuração
├── analise_matematica.ipynb    # Análise matemática com SymPy
├── backend/
│   ├── main.py                 # API FastAPI principal
│   └── requirements.txt        # Dependências Python
└── frontend/
    ├── package.json            # Configuração Node.js
    ├── public/
    │   └── index.html         # Template HTML
    └── src/
        ├── App.js             # Componente React principal
        ├── App.css            # Estilos da aplicação
        └── index.js           # Ponto de entrada React
```

### Arquivos de Dados

#### Entrada de Dados
- Endereços via interface web ou API JSON
- Parâmetros de otimização configuráveis
- Validação automática de qualidade dos endereços

#### Saída de Dados
- Resultado em formato JSON com:
  - Velocidade ótima calculada
  - Custo total estimado
  - Informações da rota (distância, tempo, coordenadas)
  - Métricas de validação

#### Acessar Dados Armazenados

##### Obter histórico de otimizações:
```python
import requests

# Histórico das últimas 10 otimizações
response = requests.get('http://localhost:8000/historico?limit=10')
historico = response.json()

for opt in historico['historico']:
    print(f"Veículo: {opt['nome_veiculo']}")
    print(f"Economia: R$ {opt['economia_rs']:.2f}")
    print("---")
```

##### Obter estatísticas gerais:
```python
# Estatísticas consolidadas
response = requests.get('http://localhost:8000/estatisticas')
stats = response.json()

print(f"Total de otimizações: {stats['total_otimizacoes']}")
print(f"Economia total: R$ {stats['economia_total_rs']:.2f}")
print(f"Economia média: R$ {stats['economia_media_rs']:.2f}")
```

##### Realizar nova otimização (salva automaticamente):
```python
# Dados salvos automaticamente no SQLite
response = requests.post("http://localhost:8000/otimizar", json={
    "nome_veiculo": "Sedan",
    "preco_combustivel": 5.50,
    "custo_hora_motorista": 25.0,
    "rota": {
        "origem": {"endereco": "São Paulo, SP"},
        "destino": {"endereco": "Rio de Janeiro, RJ"}
    }
})
result = response.json()
print(f"Economia calculada: R$ {result['economia_vs_40kmh']:.2f}")
```

##### Exportar dados para análise externa:
```python
import pandas as pd
import sqlite3

# Conectar ao banco SQLite
conn = sqlite3.connect('backend/otimizacoes.db')
df = pd.read_sql_query("SELECT * FROM otimizacoes", conn)

# Exportar para CSV
df.to_csv('historico_otimizacoes.csv', index=False)
conn.close()
```

## Estrutura de Banco de Dados

O sistema utiliza **SQLite** para persistência de dados. O banco é criado automaticamente como `otimizacoes.db`:

### Tabela Principal - otimizacoes
```sql
CREATE TABLE otimizacoes (
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
);
```

### Funcionalidades de Dados
- **Armazenamento Automático**: Todas as otimizações são salvas automaticamente
- **Histórico Completo**: API `/historico` retorna otimizações anteriores
- **Estatísticas**: API `/estatisticas` mostra economia total e médias
- **Geocodificação**: Cache temporário de coordenadas para performance
- **Rotas**: Calculadas via API OpenRouteService com validação de qualidade

## Licença

Este projeto foi desenvolvido para fins acadêmicos e de pesquisa. 

### Uso Acadêmico
- Permitido uso, modificação e distribuição para fins educacionais
- Citação dos autores originais requerida em trabalhos derivados
- Contribuições e melhorias são bem-vindas

### Uso Comercial
- Consulte os autores antes do uso comercial
- APIs de terceiros (OpenRouteService) possuem seus próprios termos de uso
- Verificar limitações de API para uso em produção

### APIs de Terceiros
- OpenRouteService: https://openrouteservice.org/terms-of-service/
- Sujeitas aos termos e limites específicos de cada provedor

## Contribuições

Contribuições são aceitas via pull requests. Para grandes mudanças, abra uma issue primeiro para discussão.

### Desenvolvimento
1. Fork o projeto
2. Crie uma branch para sua feature
3. Faça commit das mudanças
4. Push para a branch
5. Abra um Pull Request