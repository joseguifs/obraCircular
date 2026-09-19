from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from starlette.concurrency import run_in_threadpool


@dataclass(frozen=True)
class ArquivoArmazenado:
    chave_objeto: str
    mime_type: str
    tamanho_bytes: int


class ArmazenamentoLocal:
    def __init__(self, diretorio: Path) -> None:
        self.diretorio = diretorio

    async def salvar_imagem(
        self,
        anuncio_id: UUID,
        conteudo: bytes,
        mime_type: str,
    ) -> ArquivoArmazenado:
        extensao = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[mime_type]
        chave = f"anuncios/{anuncio_id}/{uuid4()}{extensao}"
        destino = self.diretorio.joinpath(*chave.split("/"))

        def escrever() -> None:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)

        await run_in_threadpool(escrever)
        return ArquivoArmazenado(
            chave_objeto=chave,
            mime_type=mime_type,
            tamanho_bytes=len(conteudo),
        )

    async def excluir(self, chave_objeto: str) -> None:
        caminho = self.diretorio.joinpath(*chave_objeto.split("/"))

        def remover() -> None:
            caminho.unlink(missing_ok=True)
            try:
                caminho.parent.rmdir()
            except OSError:
                pass

        await run_in_threadpool(remover)

    @staticmethod
    def url_publica(chave_objeto: str) -> str:
        return f"/uploads/{chave_objeto}"
