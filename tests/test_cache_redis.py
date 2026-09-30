import unittest
from unittest.mock import Mock, patch

from src import cache_redis


class CacheRedisTests(unittest.TestCase):
    @patch.object(cache_redis, "is_redis_available", return_value=True)
    def test_limpar_cache_varre_chaves_sem_keys(self, _redis_available: Mock) -> None:
        redis_client = Mock()
        redis_client.scan_iter.return_value = iter(["api_cache:a", "api_cache:b"])
        redis_client.delete.return_value = 2

        with patch.object(cache_redis, "redis_client", redis_client):
            removidas = cache_redis.limpar_cache()

        self.assertEqual(removidas, 2)
        redis_client.scan_iter.assert_called_once_with(match="api_cache:*")
        redis_client.delete.assert_called_once_with("api_cache:a", "api_cache:b")


if __name__ == "__main__":
    unittest.main()
