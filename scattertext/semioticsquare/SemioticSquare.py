import numpy as np
from scattertext.termscoring.ScaledFScore import ScaledFScorePresets

from scattertext.termranking import AbsoluteFrequencyRanker


class EmptyNeutralCategoriesError(Exception): pass


class SemioticSquare(object):
	'''
	Create a visualization of a semiotic square.  Requires Corpus to have
	at least three categories.
	>>> newsgroups_train = fetch_20newsgroups(subset='train',
	...   remove=('headers', 'footers', 'quotes'))
	>>> vectorizer = CountVectorizer()
	>>> X = vectorizer.fit_transform(newsgroups_train.data)
	>>> corpus = st.CorpusFromScikit(
	... 	X=X,
	... 	y=newsgroups_train.target,
	... 	feature_vocabulary=vectorizer.vocabulary_,
	... 	category_names=newsgroups_train.target_names,
	... 	raw_texts=newsgroups_train.data
	... 	).build()
	>>> semseq = SemioticSquare(corpus,
	... 	category_a = 'alt.atheism',
	... 	category_b = 'soc.religion.christian',
	... 	neutral_categories = ['talk.religion.misc']
	... )
	>>> # A simple HTML table
	>>> html = SemioticSquareViz(semseq).to_html()
	>>> # The table with an interactive scatterplot below it
	>>> html = st.produce_semiotic_square_explorer(semiotic_square,
	...                                            x_label='More Atheism, Less Xtnity',
	...                                            y_label='General Religious Talk')
	'''

	def __init__(self,
	             term_doc_matrix,
	             category_a,
	             category_b,
	             neutral_categories,
	             labels=None,
	             term_ranker=AbsoluteFrequencyRanker,
	             scorer=None):
		'''
		Parameters
		----------
		term_doc_matrix : TermDocMatrix
			TermDocMatrix (or descendant) which will be used in constructing square.
		category_a : str
			Category name for term A
		category_b : str
			Category name for term B (in opposition to A)
		neutral_categories : list[str]
			List of category names that A and B will be contrasted to.  Should be in same domain.
		labels : dict
			None by default. Labels are dictionary of {'a_and_b': 'A and B', ...} to be shown
			above each category.
		term_ranker : TermRanker
			Class for returning a term-frequency df
		scorer : termscoring class, optional
			Term scoring class for lexicon mining. Default: `scattertext.termscoring.ScaledFScore`
		'''
		self.term_doc_matrix_ = term_doc_matrix
		assert category_a in term_doc_matrix.get_categories()
		assert category_b in term_doc_matrix.get_categories()
		for category in neutral_categories:
			assert category in term_doc_matrix.get_categories()
		if len(neutral_categories) == 0:
			raise EmptyNeutralCategoriesError()
		self.category_a_ = category_a
		self.term_ranker = term_ranker(term_doc_matrix)
		self.category_b_ = category_b
		self.neutral_categories_ = neutral_categories
		self.scorer = ScaledFScorePresets() \
			if scorer is None else scorer
		self.axes = self._build_axes(scorer)
		self.lexicons = self._build_lexicons()
		self._labels = labels

	def get_axes(self, scorer=None):
		'''
		Returns
		-------
		pd.DataFrame
		'''
		if scorer:
			return self._build_axes(scorer)
		return self.axes

	def get_lexicons(self, num_terms=10):
		'''
		Parameters
		----------
		num_terms, int

		Returns
		-------
		dict
		'''
		return {k: v.index[:num_terms]
		        for k, v in self.lexicons.items()}

	def get_labels(self):
		a = self.category_a_
		b = self.category_b_
		default_labels = {'a': a,
		                  'not_a': 'Not ' + a,
		                  'b': b,
		                  'not_b': 'Not ' + b,
		                  'a_and_b': a + ' + ' + b,
		                  'not_a_and_not_b': 'Not ' + a + ' + Not ' + b,
		                  'a_and_not_b': a + ' + Not ' + b,
		                  'b_and_not_a': 'Not ' + a + ' + ' + b}
		labels = self._labels
		if labels is None:
			labels = {}
		return {name+'_label': labels.get(name, default_labels[name])
		        for name in default_labels}

	def _build_axes(self, scorer):
		if scorer is None:
			scorer = self.scorer
		tdf = self._get_term_doc_count_df()
		counts = tdf.sum(axis=1)
		tdf['x'] = scorer.get_scores(
			tdf[self.category_a_ + ' freq'],
			tdf[self.category_b_ + ' freq']
		)
		tdf['x'][np.isnan(tdf['x'])] = self.scorer.get_default_score()
		tdf['y'] = scorer.get_scores(
			tdf[[t + ' freq' for t in [self.category_a_, self.category_b_]]].sum(axis=1),
			tdf[[t + ' freq' for t in self.neutral_categories_]].sum(axis=1)
		)
		tdf['counts'] = counts
		return tdf[['x', 'y', 'counts']]

	def _get_term_doc_count_df(self):
		return (self.term_ranker.get_ranks()
		[[t + ' freq'
		  for t in [self.category_a_, self.category_b_] + self.neutral_categories_]])

	def _build_lexicons(self):
		self.lexicons = {}
		ax = self.axes
		x_max = ax['x'].max()
		y_max = ax['y'].max()
		x_min = ax['x'].min()
		y_min = ax['y'].min()
		baseline = self.scorer.get_default_score()

		def dist(candidates, x_bound, y_bound):
			return ((x_bound - candidates['x']) ** 2 + (y_bound - candidates['y']) ** 2).sort_values()

		self.lexicons['a'] = dist(ax[(ax['x'] > baseline) & (ax['y'] > baseline)], x_max, y_max)
		self.lexicons['not_a'] = dist(ax[(ax['x'] < baseline) & (ax['y'] < baseline)], x_min, y_min)

		self.lexicons['b'] = dist(ax[(ax['x'] < baseline) & (ax['y'] > baseline)], x_min, y_max)
		self.lexicons['not_b'] = dist(ax[(ax['x'] > baseline) & (ax['y'] < baseline)], x_max, y_min)

		self.lexicons['a_and_b'] = dist(ax[(ax['y'] > baseline)], baseline, y_max)
		self.lexicons['not_a_and_not_b'] = dist(ax[(ax['y'] < baseline)], baseline, y_min)

		self.lexicons['a_and_not_b'] = dist(ax[(ax['x'] > baseline)], x_max, baseline)

		self.lexicons['b_and_not_a'] = dist(ax[(ax['x'] < baseline)], x_min, baseline)

		return self.lexicons
