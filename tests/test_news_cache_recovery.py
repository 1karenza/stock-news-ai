import unittest
from unittest.mock import Mock

from news_cache import process_cached


class NewsCacheRecoveryTests(unittest.TestCase):
    def test_failed_scan_is_retried_then_success_is_reused(self):
        item = dict(title='Tin doanh nghiệp', url='https://example.com/news', summary='Mô tả')
        processor = Mock(side_effect=[dict(item, article_text=''),
                                     dict(item, article_text='Nội dung bài gốc đầy đủ')])
        cache = {}
        first = process_cached(item, False, 'model', cache, processor, now=100)
        self.assertEqual(first['article_text'], '')
        self.assertFalse(cache)
        second = process_cached(item, False, 'model', cache, processor, now=101)
        third = process_cached(item, False, 'model', cache, processor, now=102)
        self.assertEqual(second['article_text'], third['article_text'])
        self.assertTrue(second['article_text'])
        self.assertEqual(processor.call_count, 2)

    def test_existing_empty_cache_is_discarded_without_waiting_for_ttl(self):
        item = dict(title='Tin doanh nghiệp', url='https://example.com/news', summary='Mô tả')
        key = (item['url'], item['title'], item['summary'], False, 'model')
        cache = {key: (100, {'article_text': ''})}
        processor = Mock(return_value=dict(item, article_text='Nội dung đã khôi phục'))
        result = process_cached(item, False, 'model', cache, processor, now=101)
        self.assertEqual(result['article_text'], 'Nội dung đã khôi phục')
        processor.assert_called_once()
