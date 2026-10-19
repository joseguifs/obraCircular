# Regras de Domínio — Administrador

O administrador é um usuário comum que também possui um registro na tabela
`administradores`. O perfil administrativo não altera o status do usuário.

## Regras

- Apenas administradores autenticados, com usuário `ATIVO` e não excluído, acessam as
  rotas de `/admin` e alteram categorias.
- O perfil administrativo só pode ser concedido a usuários `ATIVO` e não excluídos.
- Um administrador não pode alterar o próprio status nem remover o próprio perfil
  administrativo; assim o sistema nunca fica sem administrador por engano.
- O administrador pode alterar o status de outros usuários (`ATIVO`, `INATIVO`,
  `BLOQUEADO`). Isso não remove pedidos, anúncios nem registros financeiros.
- O administrador pode encerrar ou excluir logicamente qualquer anúncio para moderação.
  As mesmas regras do vendedor se aplicam: exclusão lógica por `deletado_em`, anúncio
  encerrado não é reativado e pedidos existentes não são alterados.
- O primeiro administrador é criado pela linha de comando
  (`python -m app.cli.promover_administrador <email>`).
