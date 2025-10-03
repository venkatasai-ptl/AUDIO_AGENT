import openai
import os


def get_llm_response(messages, *,
                     model="gpt-4.1-mini",
                     temperature=0.4,
                     top_p=1.0,
                     stream=False):
   
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        top_p=top_p,
        messages=messages,
        stream=stream
    )
    
    if stream:
        # Return generator for streaming responses
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    else:
        # Return full response for non-streaming
        return response.choices[0].message.content