# Treino Planner

Aplicativo web responsivo local para navegar pela biblioteca de exercícios, montar planos semanais e registrar treinos concluídos. O servidor usa a biblioteca padrão do Python e SQLite e pode ser acessado por outros dispositivos na rede local.

## Organização do armazenamento

O código e o banco local ficam no filesystem Linux do WSL:

```text
/home/nique/projetos/treino-planner/                 código do aplicativo
/home/nique/projetos/treino-planner/data/metadata/library.sqlite3
                                                    banco local, ignorado pelo Git
```

O dataset é externo ao projeto e permanece no disco D:, fora do repositório. A árvore operacional usada para resolver as mídias está em `D:\Dados\TreinoPlanner\dataset-original\`, acessível no WSL por `/mnt/d/Dados/TreinoPlanner/dataset-original/`:

```text
/mnt/d/Dados/TreinoPlanner/dataset-original/        árvore operacional para resolução de mídia
└── GIFS PLANEJADOR - ORGANIZADOS/
    └── FEMININO, MASCULINO, demais categorias e arquivos
```

O servidor tenta resolver os GIFs pela árvore `dataset-original`, validando tamanho e SHA-256. Se o arquivo não estiver disponível ou não corresponder ao conteúdo esperado, a resolução pode usar o ZIP de origem registrado no banco como fallback. Os GIFs e ZIPs permanecem fora do projeto; o `.gitignore` exclui bancos locais, arquivos ZIP e arquivos GIF. Não versionar nem copiar o dataset para dentro do projeto.

### Licença e redistribuição

Os ZIPs e GIFs são conteúdo externo. Antes de redistribuí-los, publicá-los ou incluí-los em uma versão compartilhada do aplicativo, confirme a licença e obtenha a permissão necessária. O armazenamento local e a indexação não concedem direitos de redistribuição.

## Abrir no VS Code e executar

No terminal WSL:

```bash
cd /home/nique/projetos/treino-planner
code .
export TREINO_PLANNER_DATASET_ROOT=/mnt/d/Dados/TreinoPlanner/dataset-original
python3 -m app.cli serve --host 0.0.0.0 --port 8000
```

No próprio PC, abra `http://localhost:8000`. Para acessar pelo celular ou outro dispositivo na mesma rede local, use o endereço de rede do PC exibido pelo servidor, na porta `8000`. Planos e histórico são armazenados no banco do PC e aparecem no app quando acessado pelo outro dispositivo.

No Windows, o atalho `C:\Users\nique\Desktop\Treino Planner.lnk` inicia o projeto diretamente pelo `wsl.exe`, define a mesma árvore operacional e usa a porta `8000`. O Smart App Control pode permanecer ativado.

O banco padrão está em `data/metadata/library.sqlite3`, relativo à raiz do projeto. Na migração entre diretórios, preserve esse arquivo para manter biblioteca, usuários, planos e histórico. O banco mantém os caminhos dos ZIPs de origem para permitir o fallback de mídia.

Para indexar um dataset novo intencionalmente, o importador aceita arquivos ZIP ou diretórios:

```bash
python3 -m app.cli import-dataset /mnt/d/Dados/TreinoPlanner/dataset/
```

Não execute o importador como parte da migração de armazenamento: a biblioteca existente é preservada no SQLite e não precisa ser reimportada. O importador é incremental e idempotente. Cada ocorrência `ZIP + caminho interno` é preservada mesmo quando o SHA-256 da mídia se repete.

## Biblioteca e planejamento

A tela **Exercícios** consulta os GIFs reais e mantém filtros de gênero e área como metadados de origem. Os nomes dos arquivos continuam provisórios e não são tratados como nomes canônicos. A tela **Minha semana** permite selecionar usuário, plano, organizar sete dias e adicionar exercícios da biblioteca compartilhada com séries, repetições, carga, unidade, descanso e observações. A execução mínima apresenta as séries do plano e registra o treino no histórico quando finalizado. Cada usuário vê seus próprios planos e histórico, enquanto a biblioteca é compartilhada localmente.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

Os testes usam ZIPs e bancos temporários. Cobrem importação idempotente, duplicatas por conteúdo, snapshots, usuários, isolamento dos planos, migração, resets com preservação da biblioteca, exercícios e séries, além da persistência após recarregar o banco.

Validação funcional realizada em 18/10/2026, após o commit `86cf0cc`:

- Suíte Python: 25/25 testes aprovados (`python3 -m unittest discover -s tests -v`).
- Testes JavaScript: 27/27 aprovados: timer (12), fluxo de execução (6), planejador (6) e service worker (3).
- Resolução de mídia validada nos testes, incluindo caminho original, reorganização A–Z, duplicatas e fallback para ZIP.
- Conferência de 100 registros reais do banco contra `dataset-original`: os 100 arquivos foram encontrados e tiveram o SHA-256 validado.
- Servidor iniciado e página inicial respondeu HTTP 200.

## Limites desta etapa

A execução mínima de treinos está implementada, incluindo visualização das séries, GIFs e registro de treinos finalizados no histórico. A validação manual completa desse fluxo no navegador ainda precisa ser feita. Não há autenticação, sincronização entre dispositivos, progressão automática, identificação consolidada dos exercícios ou enriquecimento automático dos metadados normalizados. O aplicativo é uma ferramenta de organização e não substitui orientação profissional ou avaliação médica.
