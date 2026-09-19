from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.anuncio_imagem import AnuncioImagem
from app.models.enums import AnuncioStatus
from app.repositories.anuncio import AnuncioRepository
from app.repositories.anuncio_imagem import AnuncioImagemRepository
from app.schemas.anuncio_imagem import AnuncioImagemListResponse, AnuncioImagemResponse
from app.services.armazenamento import ArmazenamentoLocal


class AnuncioImagemService:
    def __init__(
        self,
        session: AsyncSession,
        repository: AnuncioImagemRepository | None = None,
        anuncio_repository: AnuncioRepository | None = None,
        armazenamento: ArmazenamentoLocal | None = None,
    ) -> None:
        configuracao = get_settings()
        self.session = session
        self.repository = repository or AnuncioImagemRepository(session)
        self.anuncio_repository = anuncio_repository or AnuncioRepository(session)
        self.armazenamento = armazenamento or ArmazenamentoLocal(configuracao.storage_path)
        self.max_imagens = configuracao.max_ad_images
        self.max_tamanho = configuracao.max_image_size_bytes

    async def adicionar(
        self,
        anuncio_id: UUID,
        vendedor_id: UUID,
        arquivos: list[UploadFile],
    ) -> AnuncioImagemListResponse:
        if not arquivos:
            raise self._erro_arquivo("Selecione ao menos uma imagem.", "AD_IMAGE_REQUIRED")

        chaves_salvas: list[str] = []
        try:
            async with self.session.begin():
                anuncio = await self.anuncio_repository.buscar_por_id(anuncio_id, bloquear=True)
                if anuncio is None:
                    raise AppError(
                        status_code=404,
                        detail="Anúncio não encontrado.",
                        code="AD_NOT_FOUND",
                    )
                if anuncio.vendedor_id != vendedor_id:
                    raise AppError(
                        status_code=403,
                        detail="Somente o vendedor pode adicionar imagens a este anúncio.",
                        code="AD_FORBIDDEN",
                    )
                if anuncio.status == AnuncioStatus.ENCERRADO:
                    raise self._erro_arquivo(
                        "Anúncios encerrados não podem receber imagens.",
                        "AD_CLOSED",
                    )

                proxima_ordem = await self.repository.proxima_ordem(anuncio_id)
                if proxima_ordem + len(arquivos) > self.max_imagens:
                    raise self._erro_arquivo(
                        f"Cada anúncio pode ter no máximo {self.max_imagens} imagens.",
                        "AD_IMAGE_LIMIT",
                    )

                imagens: list[AnuncioImagem] = []
                for deslocamento, arquivo in enumerate(arquivos):
                    conteudo = await arquivo.read(self.max_tamanho + 1)
                    if len(conteudo) > self.max_tamanho:
                        raise self._erro_arquivo(
                            "Cada imagem deve ter no máximo 5 MB.",
                            "AD_IMAGE_TOO_LARGE",
                        )

                    mime_type = self._detectar_tipo(conteudo)
                    if mime_type is None:
                        raise self._erro_arquivo(
                            "Envie imagens JPEG, PNG ou WebP válidas.",
                            "AD_IMAGE_INVALID_TYPE",
                        )

                    armazenado = await self.armazenamento.salvar_imagem(
                        anuncio_id,
                        conteudo,
                        mime_type,
                    )
                    chaves_salvas.append(armazenado.chave_objeto)
                    nome_original = Path(arquivo.filename or "imagem").name[:255]
                    imagens.append(
                        AnuncioImagem(
                            anuncio_id=anuncio_id,
                            chave_objeto=armazenado.chave_objeto,
                            nome_original=nome_original,
                            mime_type=armazenado.mime_type,
                            tamanho_bytes=armazenado.tamanho_bytes,
                            ordem=proxima_ordem + deslocamento,
                        )
                    )

                imagens = await self.repository.criar_varias(imagens)

            return AnuncioImagemListResponse(
                items=[self._resposta(imagem) for imagem in imagens]
            )
        except Exception:
            for chave in chaves_salvas:
                await self.armazenamento.excluir(chave)
            raise
        finally:
            for arquivo in arquivos:
                await arquivo.close()

    def _resposta(self, imagem: AnuncioImagem) -> AnuncioImagemResponse:
        return AnuncioImagemResponse(
            id=imagem.id,
            anuncio_id=imagem.anuncio_id,
            url=self.armazenamento.url_publica(imagem.chave_objeto),
            nome_original=imagem.nome_original,
            mime_type=imagem.mime_type,
            tamanho_bytes=imagem.tamanho_bytes,
            ordem=imagem.ordem,
            criado_em=imagem.criado_em,
        )

    @staticmethod
    def _detectar_tipo(conteudo: bytes) -> str | None:
        if conteudo.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if len(conteudo) >= 12 and conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
            return "image/webp"
        return None

    @staticmethod
    def _erro_arquivo(detail: str, code: str) -> AppError:
        return AppError(status_code=400, detail=detail, code=code)
