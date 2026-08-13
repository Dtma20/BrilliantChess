# 0006 — Interface em React servida pelo FastAPI

Data: 2026-08-13
Estado: aceita

## Contexto

A interface local nasceu como HTML, CSS e JavaScript sem build (ADR 0005). Isso
serviu bem enquanto eram duas paginas simples. O laboratorio de duelo mudou a
escala do problema: estado de autoplay, revisao de lances anteriores, auditoria
por portao com divulgacao progressiva, contadores por lado e teclado completo. A
versao sem framework passou a repetir logica de render em cada arquivo e a
manipular o DOM na mao para estados que sao, no fundo, uma unica arvore de
estado.

Nada disso e culpa do JavaScript sem build; e so o ponto onde uma camada de
componentes com tipos passa a pagar por si.

## Decisao

A interface passa a ser um SPA em React com TypeScript, construido com Vite,
estilizado com Tailwind CSS v4 e apoiado nos componentes do shadcn/ui. O codigo
vive em `frontend/`, isolado do pacote Python.

O FastAPI continua sendo o unico servidor: ele monta `frontend/dist/assets` e
devolve `index.html` para qualquer rota de navegacao. O roteamento de telas
acontece no navegador; o servidor nao ganhou nenhuma rota nova de pagina.

Em desenvolvimento, `npm run dev` sobe o Vite em `127.0.0.1:5173` com proxy de
`/api` para `127.0.0.1:8000`. Os dois lados continuam em loopback.

Consequencias praticas:

- os contratos JSON de `interfaces/web/schemas.py` viraram tipos TypeScript em
  `frontend/src/lib/api.ts`, escritos a mao e verificados pelos testes de API;
- nenhuma regra de xadrez foi duplicada no front: ele so transporta e desenha;
- `frontend/dist` e artefato de build e nao entra no versionamento;
- quando o build nao existe, o servidor devolve uma pagina que explica como
  gerar, em vez de erro.

## Alternativas rejeitadas

- **Manter HTML e JavaScript sem build.** Continuaria funcionando, mas a
  auditoria do laboratorio ja exigia sincronizar quatro blocos de DOM na mao a
  cada passo, sem tipos entre o contrato da API e a tela.
- **Renderizar as paginas no servidor com Jinja.** Traria a interface para
  dentro do pacote Python e misturaria apresentacao com a camada que hoje so
  fala JSON. O autoplay tambem e um problema de cliente, nao de servidor.
- **Servir o front por um segundo processo em producao.** Dois processos para um
  app local de uma pessoa so, e mais uma porta escutando. O proxy do Vite
  resolve isso apenas durante o desenvolvimento.
- **Empacotar `dist` dentro do pacote Python.** Facilitaria a distribuicao, mas
  colocaria artefato de build no versionamento. O servidor aceita esse layout se
  alguem quiser distribuir assim, so nao e o padrao do repositorio.

## Fair play

Nada muda. O aviso permanente esta no shell da aplicacao, aparece em todas as
telas e nao pode ser dispensado. O SPA continua sem qualquer ponte com partidas
ao vivo de terceiros: nao le tela, nao controla mouse, nao cria overlay e so
fala com o backend local.
