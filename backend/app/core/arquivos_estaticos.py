from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Um ano: o máximo que os navegadores costumam respeitar.
CACHE_IMUTAVEL = "public, max-age=31536000, immutable"


class ArquivosImutaveis(StaticFiles):
    """Serve arquivos que nunca mudam depois de gravados, com cache longo no navegador.

    Cada upload recebe um nome único (`uuid4`) e nunca é sobrescrito: trocar uma foto
    gera outro arquivo e outra URL. Por isso o navegador pode guardar a resposta sem
    voltar a perguntar ao servidor a cada visita. Erros (como 404) não recebem o
    cabeçalho, para um arquivo que ainda não existe não ficar "ausente" em cache.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        resposta = await super().get_response(path, scope)
        if resposta.status_code in (200, 304):
            resposta.headers["Cache-Control"] = CACHE_IMUTAVEL
        return resposta
