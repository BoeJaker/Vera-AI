Improvements:
Status Bar - in-thought, tool being used, cpu load, pool load, agent you're speaking to, api limits

Bugs:
new columns can go off-screen


Researcher - A

The current system doesnt work well whenn you select files mode and deep.

Could we allow the system to be better parallelized, each ollama instance has independent compute resources, with a focus on "run ahead" so the fast LLM can do initial research whilst the thinker looks at the broader context when both are complete the fast can synthesize the final output. the third instance is also slow but could be used to think about the output of the first.

Bear in mind the two slow instances can take up to 10-20 minutes depending on context size but the fast could probably run several times in that time - so it would be possible to have it evaluate or iterate its own results based on the streamed output of the thinker / analyzer. perhaps a better use of the third instances is analyser/orchestrator, it can look at the output of both in realtime and think of best next steps? The system should be, flexible, scalable and modular.

i need to be able to ask any mode to continue research into a topic expanding upon the iteration before perhaps diving deep into each portion. currently if i ask it a question - it researches and answers - i ask it to continue and it researches continuation rather than continuing to research.
it would be good if there was a proper iterative research mode that allowed research over multiple runs going as broad and deep as possible. Allowing the LLM to perform exploration of the internet and navigation of the web so if i ask it to research a particular website it doesnt just websearch it loads the target website and navigates it collecting information about content

Researcher - B

Could we improve the research capabilities, perhaps break it out into its own file, allowing the LLM to tuely travese results and perform research - not just synthesize output based on websearch results - your going to need to build in some more data sources, perhaps the datasources should have their own API / file. i have my local searxng instance setup as the only search resource at the moment and i think it might be using a fallback. i wouldnt mind using a docker stack to retrieve more info like common crawl archives. 

i need it to be able to use the research DB as a searchable resource.

you need to be ale to give note cells a title, also i would like notebooks to have an index of the cells contained within. we could even add a page structure - cells could be auto titled by the fast llm in downtime


Notebooks are still not visible in the library, they need to be visible alongside research

I would also like referenced sources to be stored and searchable - preferably the full content from the page

Integrate other notebooks like onenote and obsidian - integrate project .MD and tag extractor - possibly extend to filesystem diff monitoring?

the sources full data should be viewable in the UI

could you integrate onenote and obsidan as notes and local folder notes for projects in .MD and .txt backends with the ability to set multiple note backend locations - even tag them to a project or piece of research and allow existing notes to be used (optionally) as context as well as run the LLM against them to generate further content

Galaxy Graph

2D mode Jitter MUST be stopped

stream mode needs to stream updates need a context mode that can stream live context into the galaxy from user input box in chat,
can stream live event from redis as they are commited to the graph. can idepently visualise redis dataflow to nodes.
Precalibrated views like system sate, network monitor, 
save views, 


Coder & ML research playground

"predictive coding" alternative to backprop implementation
memory ml plugins

MS365 Automation and workflow implementation for an AI and automation analyst