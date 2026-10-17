# Treino Planner

Aplicativo web responsivo local para navegar pela biblioteca de exercícios, montar planos semanais e registrar treinos concluídos. O servidor usa a biblioteca padrão do Python e SQLite.

## Organização do armazenamento

O código e o banco local ficam no filesystem Linux do WSL:

```text
/home/nique/projetos/treino-planner/                 código do aplicativo
/home/nique/projetos/treino-planner/data/metadata/library.sqlite3
                                                    banco local, ignorado pelo Git
```

O dataset é externo ao projeto e permanece no disco D:, fora do repositório:

```text
/mnt/d/Dados/TreinoPlanner/dataset/                 diretório externo do dataset
└── GIFS PLANEJADOR - ORGANIZADOS-...-001.zip       10 arquivos ZIP
    ...
└── GIFS PLANEJADOR - ORGANIZADOS-...-010.zip
```

Os GIFs não são extraídos para o projeto. O banco guarda a proveniência e os caminhos absolutos dos ZIPs externos; o servidor lê um GIF do arquivo ZIP quando precisa exibi-lo. O `.gitignore` exclui bancos locais, arquivos ZIP e arquivos GIF. Não versionar nem copiar os arquivos do dataset para dentro do projeto.

### Licença e redistribuição

Os ZIPs e GIFs são conteúdo externo. Antes de redistribuí-los, publicá-los ou incluí-los em uma versão compartilhada do aplicativo, confirme a licença e obtenha a permissão necessária. O armazenamento local e a indexação não concedem direitos de redistribuição.

## Abrir no VS Code e executar

No terminal WSL:

```bash
cd /home/nique/projetos/treino-planner
code .
python3 -m app.cli serve --host 0.0.0.0 --port 8000
```

Abra `http://localhost:8000` no navegador. Não abra `index.html` diretamente pelo sistema de arquivos.

O banco padrão está em `data/metadata/library.sqlite3`, relativo à raiz do projeto. Na migração entre diretórios, preserve esse arquivo para manter biblioteca, usuários, planos e histórico. Os caminhos das dez entradas de `source_archive` devem apontar para os ZIPs em `/mnt/d/Dados/TreinoPlanner/dataset/`.

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

## Limites desta etapa

A execução mínima de treinos está implementada, incluindo visualização das séries, GIFs e registro de treinos finalizados no histórico. A validação manual completa desse fluxo no navegador ainda precisa ser feita. Não há autenticação, sincronização entre dispositivos, progressão automática, identificação consolidada dos exercícios ou enriquecimento automático dos metadados normalizados. O aplicativo é uma ferramenta de organização e não substitui orientação profissional ou avaliação médica.
